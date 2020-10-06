import os
import numpy as np
import pylab as plt
import astropy.table
from desimeter.desimeter import Desimeter
import fitsio

def outline_petals(petals=None, **kwargs):
    '''
    kwargs: matplotlib plot() kwargs.
    '''
    th = np.linspace(0,np.pi/5,100)
    if petals is None:
        petals = list(range(10))
    for i in petals:
        oth = np.deg2rad(i*36)
        r1 = 420
        r0 = 40
        plt.plot(r1*np.cos(oth+th), r1*np.sin(oth+th), '-', **kwargs)
        plt.plot(r0*np.cos(oth+th), r0*np.sin(oth+th), '-', **kwargs)
        plt.plot([r0*np.cos(oth+th[0]), r1*np.cos(oth+th[0])],
                 [r0*np.sin(oth+th[0]), r1*np.sin(oth+th[0])], '-', **kwargs)
        plt.plot([r0*np.cos(oth+th[-1]), r1*np.cos(oth+th[-1])],
                 [r0*np.sin(oth+th[-1]), r1*np.sin(oth+th[-1])], '-', **kwargs)

def plot_fiducial_offsets(table, expnum=-1, frame=-1):
    # Takes an "fvc-spots" table
    from desimeter.twrapper import Twrapper
    T = Twrapper(table)
    # Find fiducials (3-4 pinholes per fiducial)
    F = T[T.pinhole_id > 0]
    # Compute a "device id" that is unique across the focal plane
    F.devid = F.device_loc + F.petal_loc * 1000
    devs = np.unique(F.devid)

    # Average pinholes per device.
    F.dev_x    = np.zeros(len(F), np.float32)
    F.dev_y    = np.zeros(len(F), np.float32)
    F.dev_stdx = np.zeros(len(F), np.float32)
    F.dev_stdy = np.zeros(len(F), np.float32)
    F.dev_dx   = np.zeros(len(F), np.float32)
    F.dev_dy   = np.zeros(len(F), np.float32)
    idevs = []
    for d in devs:
        I = np.flatnonzero(F.devid == d)
        F.dev_x[I] = np.mean(F.x_fp[I])
        F.dev_y[I] = np.mean(F.y_fp[I])
        dx = F.x_fp[I] - F.x_fp_metro[I]
        dy = F.y_fp[I] - F.y_fp_metro[I]
        F.dev_dx[I] = np.mean(dx)
        F.dev_dy[I] = np.mean(dy)
        F.dev_stdx[I] = np.std(dx)
        F.dev_stdy[I] = np.std(dy)
        idevs.append(I[0])
        #plt.clf()
        #plt.plot(F.x_fp[I], F.y_fp[I], 'b.')
        #plt.plot(F.x_fp_metro[I], F.y_fp_metro[I], 'r.')
        #plt.show()
    D = F[np.array(idevs)]

    for i in range(len(D)):
        if D.device_loc[i] in [541, 542]:
            print('GIF % 4i' % D.location[i], 'dx,dy',
                  '%+.3f, %+.3f' % (D.dev_dx[i], D.dev_dy[i]))

    for p in np.unique(D.petal_loc):
        I = np.flatnonzero(D.petal_loc == p)
        plt.plot(D.dev_x[I], D.dev_y[I], 'o', mec='none', ms=25, alpha=0.1)
        #plt.text(np.mean(D.dev_x[I]), np.mean(D.dev_y[I]), 'Petal loc %i' % p)
        th = np.arctan2(np.mean(D.dev_y[I]), np.mean(D.dev_x[I]))
        pp = int(np.round((th / (2.*np.pi / 10.)) - 0.5))
        pth = (pp + 0.5) * (2.*np.pi/10.)
        R = 300.
        plt.text(np.cos(pth)*R, np.sin(pth)*R, 'Petal loc %i' % p)
    #for x,y,d in zip(D.dev_x, D.dev_y, D.devid):
    #    plt.text(x, y, '%i' % d)
    qargs = dict(pivot='middle', angles='xy', scale_units='xy',
                 scale=0.0005)
    Q = plt.quiver(D.dev_x, D.dev_y, D.dev_dx, D.dev_dy, **qargs)
    # add quiver scale marker!
    sx = 20
    plt.quiverkey(Q, -400, 400, sx/1000., '%i um' % sx, coordinates='data')
    # Draw lines around the petals.
    outline_petals(color='k', alpha=0.1)
    plt.axis('equal')
    rms2d = 1000. * np.sqrt(np.mean(D.dev_dx**2 + D.dev_dy**2))
    plt.title('Offsets of fiducials vs whole-focal-plane fit: %.1f um RMS2d, expnum %i frame %i' % (rms2d, expnum, frame))
    return D

if __name__ == '__main__':
    plt.figure(figsize=(10,10))

    dm = Desimeter(proc_data_dir='proc')

    fidfn = 'fiducials.fits'
    if not os.path.exists(fidfn):
        fids = []
        # All exposures on 2020-03-14,15
        for keep,expnum in [(False, 52644)] + [(True, e) for e in list(range(55353, 55692+1))]:
        #for expnum in [52644] + list(range(55353, 55357+1)):
            fvcfn = dm.find_file('fvc', expnum=expnum)
            if fvcfn is None:
                continue
            print('Expnum', expnum)
            print('FVC', fvcfn)
            frame = 0
            fn = dm.find_file('fvc-spots', expnum=expnum, frame=frame)
            if os.path.exists(fn):
                spots = astropy.table.Table.read(fn)
            else:
                spots = dm.measure_spots(expnum, frame)
                spots.write(fn, overwrite=True)
            spots = dm.refit_spots(spots)
            #print('Fit fvc2fp transform:', dm.fvc2fp.tojson())
            plt.clf()
            D = plot_fiducial_offsets(spots, expnum=expnum, frame=frame)
            fn = 'fvc-fid-offsets-%08i-F%04i.png' % (expnum, frame)
            plt.savefig(fn)
            print('Wrote', fn)
            plt.clf()
            if not keep:
                continue
            # Format table of per-fiducial results
            D.expnum = np.zeros(len(D), np.int32) + expnum
            D.frame  = np.zeros(len(D), np.int16) + frame
            hdr = fitsio.read_header(fvcfn)
            for key in ['MJD-OBS', 'TARGTRA', 'TARGTDEC', 'TARGTAZ', 'TARGTEZ', 'AIRMASS',
                        'ADC1PHI', 'ADC2PHI']:
                D.set(key.replace('-','_').lower(), np.zeros(len(D), np.float32) + hdr.get(key, -99))
            fids.append(D._table)
        fids = astropy.table.vstack(fids)
        fids.write('fiducials.fits', overwrite=True)
    else:
        fids = astropy.table.Table.read(fidfn)

    from desimeter.twrapper import Twrapper
    fids = Twrapper(fids)
    print(len(fids), 'fiducial measurements,', len(np.unique(fids.devid)), 'unique fids')
    d = np.hypot(fids.dev_dx, fids.dev_dy)
    I = np.flatnonzero(d < 0.1)
    fids = fids[I]
    print('Cut to', len(fids), 'based on residuals')

    # Plots wrt some observing properties.
    X = fids[fids.devid == 1542]
    X.dx = X.dev_dx * 1000.
    X.dy = X.dev_dy * 1000.
    tt = 'Fiducial 1542, 2020-03-(14,15)'
    X.adc_dphi = np.fmod(360 + X.adc2phi-X.adc1phi, 360)

    for k in ('airmass', 'expnum', 'adc_dphi'):
        plt.clf()
        plt.plot(X.get(k), X.dx, 'b.', label='dx')
        plt.plot(X.get(k), X.dy, 'r.', label='dy')
        plt.title(tt)
        plt.legend()
        plt.xlabel(k)
        plt.ylabel('Fiducial offset (um)')
        plt.savefig('fid-%s.png' % k)

    M = Twrapper(dm.metro)
    print('Metrology columns:', M.get_columns())

    applied_dx = []
    applied_dy = []

    devids = np.unique(fids.devid)
    for d in devids:
        I = np.flatnonzero(fids.devid == d)
        # drop largest and smallest dx,dy (cheap 'sigma-clipping')
        dx = 1000. * fids.dev_dx[I]
        dy = 1000. * fids.dev_dy[I]
        print(len(I), 'measurements for dev', d, 'with mean dx,dy  %+5.1f, %+5.1f and std %4.1f, %4.1f' %
              (np.mean(dx), np.mean(dy), np.std(dx), np.std(dy)))
        Kx = np.argsort(dx)
        Ky = np.argsort(dy)
        dx = dx[Kx[1:-1]]
        dy = dy[Ky[1:-1]]
        print('After dropping min & max:', len(dx), 'meas, mean dx,dy %+5.1f, %+5.1f and std %4.1f, %4.1f' %
              (np.mean(dx), np.mean(dy), np.std(dx), np.std(dy)))
        dx = np.mean(dx) / 1000.
        dy = np.mean(dy) / 1000.

        IM = np.flatnonzero(M.location == d)
        print(len(IM), 'metrology entries for location', d, M.device_type[IM[0]])
        #print('Metro x_fp,y_fp', M.x_fp[IM], M.y_fp[IM])
        #print('Fid x_fp, y_fp:', fids.dev_x[I], fids.dev_y[I])

        applied_dx.append(dx)
        applied_dy.append(dy)

        M.x_fp[IM] += dx
        M.y_fp[IM] += dy

    petals = devids // 1000
    applied_dx = np.array(applied_dx)
    applied_dy = np.array(applied_dy)
    for p in np.unique(petals):
        I = np.flatnonzero(petals == p)
        print('Petal', p, ': average dx,dy %.1f, %.1f um' %
              (1000. * np.mean(applied_dx[I]), 1000. * np.mean(applied_dy[I])))

    outdir = 'dm-fid-sys'
    dm.write_desimeter(outdir)


    # Check!
    newdm = Desimeter(desimeter_dir=outdir, proc_data_dir='proc-fid-sys')
    for expnum in [52644] + list(range(55353, 55357+1)):
        fvcfn = newdm.find_file('fvc', expnum=expnum)
        if fvcfn is None:
            continue
        print('Expnum', expnum)
        print('FVC', fvcfn)
        frame = 0
        fn = newdm.find_file('fvc-spots', expnum=expnum, frame=frame)
        if os.path.exists(fn):
            spots = astropy.table.Table.read(fn)
        else:
            spots = newdm.measure_spots(expnum, frame)
            spots.write(fn, overwrite=True)
        # At first I thought we could get away without Z-B, or a constant Z-B, but that very
        # much does not work due to, I assume, how different offsets & scales interact with Z-B.
        # Zero out the Z-B corrections (zbfit=False does not touch them)
        #newdm.fvc2fp.zbcoeffs = newdm.fvc2fp.zbpolids = None
        #spots = newdm.refit_spots(spots, zbfit=False)
        spots = newdm.refit_spots(spots)
        D = plot_fiducial_offsets(spots, expnum=expnum, frame=frame)
        fn = 'fvc-fid-sys-%08i-F%04i.png' % (expnum, frame)
        plt.savefig(fn)
        print('Wrote', fn)
        plt.clf()
