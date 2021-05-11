#!/usr/bin/env python

import numpy as np

from desimeter.transform.radec2tan import radec2tan,hadec2xy,hadec2altaz,tan2radec
from desimeter.transform.tan2fp.raytracefit import tan2fp,fp2tan
from desimeter.trig import sincosd

def _measure_fieldrot_deg(ha,dec,tel_ha,tel_dec,xfp_mm,yfp_mm) :

    ok = (~(np.isnan(ha*dec*xfp_mm*yfp_mm)))&(xfp_mm**2+yfp_mm**2>10**2)
    x2,y2=hadec2xy(ha[ok],dec[ok],tel_ha,tel_dec) # rad
    return np.rad2deg(np.mean((yfp_mm[ok]*x2-xfp_mm[ok]*y2)/np.sqrt((xfp_mm[ok]**2+yfp_mm[ok]**2)*(x2**2+y2**2))))


def fiberassign_radec2xy(ra,dec,tile_ra,tile_dec,tile_mjd,tile_ha,tile_fieldrot,adc1,adc2) :

    # LST from HA
    lst=tile_ha+tile_ra

    # start with pointing = tile center
    tel_ra=tile_ra+0.
    tel_dec=tile_dec+0.

    # tune telescope pointing given ADC angle
    # in order to fp coordinates of tile RA and DEC, it's not zero because of the ADC angles
    for iteration in range(2) :

        xtan,ytan = radec2tan(np.array([tile_ra]),np.array([tile_dec]),tel_ra,tel_dec,tile_mjd,lst,hexrot_deg=0)
        xfp_0,yfp_0   = tan2fp(xtan,ytan,adc1,adc2) #mm
        #print("Temp tile center in FP coordinates = {},{} mm".format(xfp_0[0],yfp_0[0]))

        # numeric derivative
        eps = 1./3600. #
        xtan,ytan = radec2tan(np.array([tile_ra+eps]),np.array([tile_dec]),tel_ra,tel_dec,tile_mjd,lst,hexrot_deg=0)
        xfp_dra,yfp_dra   = tan2fp(xtan,ytan,adc1,adc2) #mm
        xtan,ytan = radec2tan(np.array([tile_ra]),np.array([tile_dec+eps]),tel_ra,tel_dec,tile_mjd,lst,hexrot_deg=0)
        xfp_ddec,yfp_ddec   = tan2fp(xtan,ytan,adc1,adc2) #mm
        dxdra=(xfp_dra[0]-xfp_0[0])/eps
        dydra=(yfp_dra[0]-yfp_0[0])/eps
        dxddec=(xfp_ddec[0]-xfp_0[0])/eps
        dyddec=(yfp_ddec[0]-yfp_0[0])/eps
        J=[[dxdra,dxddec],[dydra,dyddec]]

        # solve linear system to get tile RA Dec at center of fov
        Jinv=np.linalg.inv(J)
        X=Jinv.dot([xfp_0[0],yfp_0[0]])
        dra=X[0]
        ddec=X[1]

        # apply offset to telescope pointing
        tel_ra += dra
        tel_dec += ddec

    # verify
    xtan,ytan = radec2tan(np.array([tile_ra]),np.array([tile_dec]),tel_ra,tel_dec,tile_mjd,lst,hexrot_deg=0)
    xfp_0,yfp_0   = tan2fp(xtan,ytan,adc1,adc2) #mm
    print("Tile center in FP coordinates = {},{} mm".format(xfp_0[0],yfp_0[0]))

    # now compute coordinates of all targets
    xtan,ytan = radec2tan(ra,dec,tel_ra,tel_dec,tile_mjd,lst,hexrot_deg=0)
    tmp_xfp,tmp_yfp = tan2fp(xtan,ytan,adc1,adc2)

    # measure field rotation
    tmp_fieldrot = _measure_fieldrot_deg(-ra,dec,-tile_ra,tile_dec,tmp_xfp,tmp_yfp)

    # apply field rotation to match request
    drot = tile_fieldrot-tmp_fieldrot
    s,c = sincosd(drot)
    xfp = c * tmp_xfp - s * tmp_yfp
    yfp = s * tmp_xfp + c * tmp_yfp

    # verify
    realised_fieldrot = _measure_fieldrot_deg(-ra,dec,-tile_ra,tile_dec,xfp,yfp)
    print("Requested fieldrot={:3.1f} arcsec delta={:3.1f} arcsec".format(tile_fieldrot*3600.,(tile_fieldrot-realised_fieldrot)*3600.))

    return xfp,yfp
