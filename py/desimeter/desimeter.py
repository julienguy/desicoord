import os

from desimeter.detectspots import detectspots
from desimeter.findfiducials import findfiducials
from desimeter.transform.fvc2fp import FVC2FP
from desimeter.io import fvc2fp_filename, load_metrology
from desimeter.match import match_same_system
from desimeter.circles import fit_circle
from desimeter.transform.xy2qs import xy2uv, uv2xy
from desimeter.io import desimeter_data_dir

from astropy.table import Table

import fitsio
import numpy as np

class Desimeter(object):
    def __init__(self, desimeter_dir=None, data_dir=None, proc_data_dir=None):
        '''
        desimeter_dir: directory containing metrology and other Desimeter state files.
        data_dir: directory containing data from the DESI spectrographs & FVC.
        proc_data_dir: directory containing intermediate processed results.
        '''
        if desimeter_dir is None:
            desimeter_dir = desimeter_data_dir()
        self.desimeter_dir = desimeter_dir

        fn = os.path.join(self.desimeter_dir, 'init-fvc2fp.json')
        self.fvc2fp = FVC2FP.read_jsonfile(fn)
        fn = os.path.join(self.desimeter_dir, 'fp-metrology.csv')
        self.metro = Table.read(fn)

        if not "LOCATION" in self.metro.keys() :
            # add useful location keyword
            self.metro["LOCATION"] = np.array(self.metro["PETAL_LOC"])*1000+np.array(self.metro["DEVICE_LOC"])

        if data_dir is None:
            data_dir = '.'
        self.data_dir = data_dir

        if proc_data_dir is None:
            proc_data_dir = '.'
        self.proc_dir = proc_data_dir

    def find_file(self, filetype, expnum=None, frame=None,
                  tag=None):
        if filetype == 'fvc':
            fn = os.path.join(self.data_dir, 'fvc-%08d.fits.fz' % expnum)
            return fn
        if filetype == 'fvc-spots':
            fn = os.path.join(self.proc_dir,
                              'fvc-spots-%08d-F%04d.fits' % (expnum, frame))
            return fn
        if filetype == 'fvc-circles':
            fn = os.path.join(self.proc_dir,
                              'fvc-circles-%08d-%s.fits' % (expnum, tag))
            return fn
        raise RuntimeError('Unknown file type "%s"' % filetype)

    def measure_spots(self, expnum, frame):
        infn = self.find_file('fvc', expnum=expnum)
        F = fitsio.read(infn, ext='F%04i' % frame)

        spots = detectspots(F, nsig=7, psf_sigma=1.)
        #threshold=500., 
        spots = findfiducials(spots,
                              input_transform_func=self.fvc2fp,
                              metrology=self.metro,
                              pinhole_max_separation_mm=1.5)
        print(spots.info)
    
        self.fvc2fp.fit(spots, update_spots=True, zbfit=True, fixed_scale=False, fixed_rotation=False)
        print(spots.info)

        # select spots that are not already matched
        selection  = (spots["LOCATION"]==-1)

        # match
        indices_of_expected_pos,distances = match_same_system(spots["X_FP"][selection],spots["Y_FP"][selection],self.metro["X_FP"],self.metro["Y_FP"])

        max_match_distance = 7
        is_matched = (distances<max_match_distance)&(indices_of_expected_pos>=0)
        ii=np.where(selection)[0]
        selection[ii]          &=  is_matched
        indices_of_expected_pos = indices_of_expected_pos[is_matched]
        distances               = distances[is_matched]

        # add columns after matching fibers
        for k1,k2 in zip(["X_FP","Y_FP"],["X_FP_EXP","Y_FP_EXP"]) :
            if k2 not in spots.keys() : spots[k2] = np.zeros(len(spots))
            spots[k2][selection]=self.metro[k1][indices_of_expected_pos]
        for k in ["EXP_Q_0","EXP_S_0","PETAL_LOC","DEVICE_LOC","LOCATION"] :
            if k in self.metro.keys() :
                if k not in spots.keys() : spots[k] = np.zeros(len(spots))
                spots[k][selection]=self.metro[k][indices_of_expected_pos]

        # for spots with metrology X_FP_EXP=X_FP_METRO
        selection = (spots["X_FP_METRO"]!=0)
        spots["X_FP_EXP"][selection]=spots["X_FP_METRO"][selection]
        selection = (spots["Y_FP_METRO"]!=0)
        spots["Y_FP_EXP"][selection]=spots["Y_FP_METRO"][selection]
    
        # Lots of those with poor matches are bad spots -- eg cosmic rays or something
        #dist = np.hypot(spots['X_FP_EXP'] - spots['X_FP'], spots['Y_FP_EXP'] - spots['Y_FP'])
        #bad = np.flatnonzero(dist > 50)
        return spots

    def measure_circles(self, allspots, do_plot=False, nmaxplot=10):
        x={}
        y={}
        xexp={}
        yexp={}
        first=True
        for spots in allspots:
            t = spots
            selection=(spots["LOCATION"]>0)
            location_and_pinhole=(np.array(t["LOCATION"])*10+np.array(t["PINHOLE_ID"])).astype(int)
            if first :
                for loc in location_and_pinhole[selection] :
                    x[loc] = []
                    y[loc] = []
                    xexp[loc] = float(t["X_FP_EXP"][location_and_pinhole==loc][0])
                    yexp[loc] = float(t["Y_FP_EXP"][location_and_pinhole==loc][0])
                    #print(loc,xexp[loc],yexp[loc])
                first=False
        
            for loc in location_and_pinhole[selection] :
                ii = np.where(location_and_pinhole==loc)[0]
                if ii.size > 1 :
                    print("several matched for LOCATION ",loc)
                    continue
                i=ii[0]
                if not loc in x.keys() :
                    x[loc] = []
                    y[loc] = []
                    xexp[loc] = float(t["X_FP_EXP"][location_and_pinhole==loc][0])
                    yexp[loc] = float(t["Y_FP_EXP"][location_and_pinhole==loc][0])
                x[loc].append(float(t["X_FP"][i]))
                y[loc].append(float(t["Y_FP"][i]))
        
        location_and_pinhole=np.array(list(x.keys()),dtype=int)
        location=location_and_pinhole//10
        pinhole=location_and_pinhole%10
        print("number of positioners:",np.sum(pinhole==0))
        print("number of fiducials:",np.sum(pinhole==1))
        print("number of pinholes:",np.sum(pinhole>=1))
        ndots=len(location_and_pinhole)
        theta=np.linspace(0,2*np.pi,50)
        xfp_metro=np.zeros(ndots)
        yfp_metro=np.zeros(ndots)
        xfp_meas=np.zeros(ndots)
        yfp_meas=np.zeros(ndots)
        count=0
        for iloc,loc in enumerate(x.keys()) :
            if len(x[loc])<6 : continue
            x[loc]=np.array(x[loc])
            y[loc]=np.array(y[loc])
            ii=np.where(x[loc]!=0)[0]
            x[loc]=x[loc][ii]
            y[loc]=y[loc][ii]
            if pinhole[iloc] == 0 and np.std(x[loc])<1. :
                # this is a non-moving positioner, I don't use this
                continue
            count += 1
            
            xc=np.median(x[loc])
            yc=np.median(y[loc])
        
            if pinhole[iloc] == 0 : # it's a positioner
                # here is the fit
                try:
                    #- Transform to curved focal surface which is closer to a real circle
                    x_cfs, y_cfs = xy2uv(x[loc], y[loc])
                    #- Do the fit
                    xc_cfs,yc_cfs,r = fit_circle(x_cfs, y_cfs)
                    #- Convert center back into CS5 x,y
                    xc, yc = uv2xy(xc_cfs, yc_cfs)
                except ValueError:
                    print("fit circle failed for loc={} x={} y={}".format(loc,xc,yc))
                    continue
        
                if iloc%100==0 :
                    print("{}/{} loc={} x={} y={} r={}".format(iloc,len(x),loc,xc,yc,r))
                if r<0.1 : continue
        
                if do_plot and count<nmaxplot :
                    plt.figure("circles")
                    plt.plot(x[loc],y[loc],"o")
                    plt.plot(xexp[loc],yexp[loc],"x")
                    theta=np.linspace(0,2*np.pi,50)
                    plt.plot(xc+r*np.cos(theta),yc+r*np.sin(theta),"-",color="green")
                    plt.plot(xc,yc,"+",color="green")
            xfp_metro[iloc]=xexp[loc]
            yfp_metro[iloc]=yexp[loc]
            xfp_meas[iloc]=xc
            yfp_meas[iloc]=yc
        dx=xfp_meas-xfp_metro
        dy=yfp_meas-yfp_metro
        dr=np.sqrt(dx**2+dy**2)
        print("median offset = %4.1f um" % (np.median(dr[dr!=0])*1000.));
        ii=np.where((xfp_metro!=0)&(dr<3.))[0]
        
        # make a table out of that
        t2=Table([location[ii],pinhole[ii],xfp_metro[ii],yfp_metro[ii],xfp_meas[ii],yfp_meas[ii]],names=["LOCATION","PINHOLE_ID","X_FP_METRO","Y_FP_METRO","X_FP","Y_FP"],dtype=[int,int,float,float,float,float])
        return t2
