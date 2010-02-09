##############################################################################
"""
T. Trainor (tptrainor@alaska.edu)
Frank Heberling (Frank.Heberling@ine.fzk.de)

Functions for extracting ctr data from ScanData objects

Modifications:
--------------
"""
##############################################################################
"""
Notes
------

References:
E. Vlieg, J. Appl. Cryst. (1997). 30, 532-543
C. Schlepuetz et al, Acta Cryst. (2005). A61, 418-425

Todo
----
- Test!
- averaging/merging and merge statistics
- keep track of Ibgr, allow plotting I and Ibgr
- corrections for rocking scans
"""
##############################################################################

import types, copy
import numpy as num
from matplotlib import pyplot

import plotter
from   mathutil import cosd, sind, tand
from   mathutil import arccosd, arcsind, arctand

import image_data
from   xtal.active_area import active_area
import gonio_psic 

##############################################################################
def ctr_data(scans,ctr=None,I=None,Inorm=None,Ierr=None,
             corr_params=None,scan_type=None):
    """
    create a ctr instance or add scan data to an existing instance
    """
    if ctr == None:
        # check for defaults
        if I==None: I ='I_c'
        if Inorm==None: Inorm='Io'
        if Ierr==None: Inorm='Ierr_c',
        if corr_params==None: corr_params={}
        if scan_type==None:scan_type='image'
        return CtrData(scans=scans,I=I,Inorm=Inorm,Ierr=Ierr,
                       corr_params=corr_params,scan_type=scan_type)
    else:
        ctr.append_scans(scans,I=I,Inorm=Inorm,Ierr=Ierr,
                         corr_params=corr_params,scan_type=scan_type)
    
##############################################################################
class CtrData:
    """
    CTR data

    scans = list of scan data instances

    I = string label corresponding to the intensity array, ie
        let y be the intensity, then y = scan[I]

    Inorm=string label corresponding to the normalization intensity array, ie
        norm = scan[Inorm], where the normalized intensity is taken as
           ynorm= y/norm

    Ierr = string label corresponding to the intensity error array, ie
        y_err = scan[Ierr].  We assume these are standard deviations 
        of the intensities (y).
        
      Note when the data are normalized we assume the statistics of norm 
        go as norm_err = sqrt(norm).  Therefore the error of normalized
        data is
           ynorm_err = ynorm * sqrt( (y_err/y)^2 + (norm_err/(norm))^2 )
                     = ynorm * sqrt( (y_err/y)^2 + 1/norm )
        If its assumed that y_err = sqrt(y) then the expression could be
        simplified futher, but we wont make that assumption since there
        may be other factors that determine how yerr was calculated.  

    corr_params = a dictionary containing the necessary information for
                  data corrections.
        corr_params['geom'] = Type of goniometer geometry ('psic' is default)
        corr_params['beam_slits'] = dictionary describing the beam slits,e.g.
                                    {'horz':.6,'vert':.8}
        corr_params['det_slits'] = dictionary describing the beam slits,e.g.
                                    {'horz':.6,'vert':.8}
        corr_params['sample'] = either dimater of round sample, or dictionary
                                describing the sample shape.
        corr_params['scale'] = scale factor to multiply by all the intensity
                               values. e.g.  if Io ~ 1million cps
                               then using 1e6 as the scale makes the normalized
                               intensity close to cps.  ie y = scale*y/norm

        See the Correction class for more info...

    scan_type = Type of scans (e.g. 'image', 'phi', etc..)
    
    """
    ##########################################################################
    def __init__(self,scans=[],I='I_c',Inorm='io',Ierr='Ierr_c',
                 corr_params={},scan_type='image'):
        #
        self.fig    = None
        self.cursor = None
        self.scan   = []
        self.scan_index  = []
        #
        self.labels      = {'I':[],'Inorm':[],'Ierr':[]}
        self.corr_params = []
        self.scan_type   = []
        #
        self.H     = num.array([],dtype=float)
        self.K     = num.array([],dtype=float)
        self.L     = num.array([],dtype=float)
        self.I     = num.array([],dtype=float)
        self.Inorm = num.array([],dtype=float)
        self.Ierr  = num.array([],dtype=float)
        self.ctot  = num.array([],dtype=float)
        self.F     = num.array([],dtype=float)
        self.Ferr  = num.array([],dtype=float)
        #
        self.append_scans(scans,I=I,Inorm=Inorm,Ierr=Ierr,
                          corr_params=corr_params,
                          scan_type=scan_type)

    ##########################################################################
    def __repr__(self,):
        lout = "CTR DATA\n"
        lout = "%sNumber of scans = %i\n" % (lout,len(self.scan))
        lout = "%sNumber of structure factors = %i\n" % (lout,len(self.L))
        return lout

    ##########################################################################
    def append_scans(self,scans,I=None,Inorm=None,Ierr=None,
                     corr_params=None,scan_type=None):
        """
        scans is a list of scan data objects.

        The rest of the arguments (defined above)
        should be the same for each scan in the list.

        For any argument with None passed we use previous vals...
        """
        if type(scans) != types.ListType:
            scans = [scans]
        
        # if None passed use the last values
        if I == None:           I = self.labels['I'][-1]
        if Inorm == None:       Inorm = self.labels['Inorm'][-1]
        if Ierr == None:        Ierr = self.labels['Ierr'][-1]
        if corr_params == None: corr_params = self.corr_params[-1]
        if scan_type == None:   scan_type = self.scan_type[-1]

        # get all the data parsed out of each scan and append
        for scan in scans:
            data = self._scan_data(scan,I,Inorm,Ierr,corr_params,scan_type)
            if data == None: return

            #self.scan.append([])
            self.scan.append(scan)
            #
            self.scan_index.extend(data['scan_index'])
            self.labels['I'].extend(data['I_lbl'])
            self.labels['Inorm'].extend(data['Inorm_lbl'])
            self.labels['Ierr'].extend(data['Ierr_lbl'])
            self.corr_params.extend(data['corr_params'])
            self.scan_type.extend(data['scan_type'])
            #
            self.H     = num.append(self.H,data['H'])
            self.K     = num.append(self.K,data['K'])
            self.L     = num.append(self.L,data['L'])
            self.I     = num.append(self.I,data['I'])
            self.Inorm = num.append(self.Inorm,data['Inorm'])
            self.Ierr  = num.append(self.Ierr,data['Ierr'])
            self.ctot  = num.append(self.ctot,data['ctot'])
            self.F     = num.append(self.F,data['F'])
            self.Ferr  = num.append(self.Ferr,data['Ferr'])

    ##########################################################################
    def _scan_data(self,scan,I,Inorm,Ierr,corr_params,scan_type):
        """
        parse scan into data...
        """
        data = {'scan_index':[],'I_lbl':[],'Inorm_lbl':[],
                'Ierr_lbl':[],'corr_params':[],'scan_type':[],
                'H':[],'K':[],'L':[],'I':[],'Inorm':[],'Ierr':[],
                'ctot':[],'F':[],'Ferr':[]}

        # compute a scan index
        scan_idx = len(self.scan)
        
        # image scan -> each scan point is a unique HKL
        if scan_type == 'image':
            if scan.image._is_integrated == False:
                scan.image.integrate()
            npts = int(scan.dims[0])
            for j in range(npts):
                data['scan_index'].append((scan_idx,j))
                data['I_lbl'].append(I)
                data['Inorm_lbl'].append(Inorm)
                data['Ierr_lbl'].append(Ierr)
                data['corr_params'].append(corr_params)
                data['scan_type'].append(scan_type)
                #
                data['H'].append(scan['H'][j])
                data['K'].append(scan['K'][j])
                data['L'].append(scan['L'][j])
                # get F
                d = image_point_F(scan,j,I=I,Inorm=Inorm,
                                  Ierr=Ierr,corr_params=corr_params)
                data['I'].append(d['I'])
                data['Inorm'].append(d['Inorm'])
                data['Ierr'].append(d['Ierr'])
                data['ctot'].append(d['ctot'])
                data['F'].append(d['F'])
                data['Ferr'].append(d['Ferr'])
        return data

    ##########################################################################
    def integrate_point(self,idx,**kw):
        """
        (Re)-integrate an individual structure factor point
        idx is the index number of the point

        If scan type is image use the following kw arguments
        (if the argument is not passed the existing value is used,
        ie just use these to update parameters)

        roi
        rotangle
        bgr_params
        plot
        fig
        bad:  True/False
        # 
        I
        Inorm
        Ierr
        corr_params
        
        """
        if idx not in range(len(self.L)): return

        if self.scan_type[idx]=="image":
            (scan_idx,point) = self.scan_index(idx)
            scan = self.scan[scan_idx]
            if scan.image._is_init() == False:
                scan.image._init_image()
            # parse integration parameters
            roi        = kw.get('roi')
            rotangle   = kw.get('rotangle')
            bgr_params = kw.get('bgr_params')
            bad_points = kw.get('bad')
            plot       = kw.get('plot',False)
            fig        = kw.get('fig')
            if bad != None:
                if bad == True:
                    if point not in scan.image.bad_points:
                        scan.image.bad_points.append(point)
                elif bad == False:
                    if point in scan.image.bad_points:
                        scan.image.bad_points.remove(point)
                else:
                    print "Warning: bad should be True/False"
            # integrate the scan.  note changes should stick...
            scan.integrate(idx=[point],roi=roi,rotangle=rotangle,
                           brg_params=bgr_params,plot=plot,fig=fig)
            # parse all the correction info and re-compute 
            I       = kw.get('I',self.labels['I'][idx])
            Inorm   = kw.get('Inorm',self.labels['Inorm'][idx])
            Ierr    = kw.get('Ierr', self.labels['Ierr'][idx])
            corr_params = kw.get('corr_params',self.corr_params[idx])
            d = image_point_F(scan,point,I=I,Inorm=Inorm,
                              Ierr=Ierr,corr_params=corr_params)
            # store results
            self.labels['I'][idx]     = I_lbl
            self.labels['Inorm'][idx] = Inorm_lbl
            self.labels['Ierr'][idx]  = Ierr_lbl
            self.corr_params[idx]     = corr_params
            self.H[idx]               = scan['H'][point]
            self.K[idx]               = scan['K'][point]
            self.L[idx]               = scan['L'][point]
            self.I[idx]               = d['I']
            self.Inorm[idx]           = d['Inorm']
            self.Ierr[idx]            = d['Ierr']
            self.ctot[idx]            = d['ctot']
            self.F[idx]               = d['F']
            self.Ferr[idx]            = d['Ferr']
        return 

    ##########################################################################
    def plot(self,fig=None,num_col=2,cursor=True,verbose=True):
        """
        plot the raw structure factor data
        """
        hksets  = sort_data(self)
        nset    = len(hksets)
        num_col = float(num_col)
        num_row = num.ceil(nset/num_col)
        pyplot.figure(fig)
        pyplot.clf()
        for j in range(nset):
            pyplot.subplot(num_row,num_col,j+1)
            d = hksets[j]
            title = 'H=%2.3f,K=%2.3f' % (d['H'][0],d['K'][0])
            pyplot.title(title, fontsize = 12)
            pyplot.plot(d['L'],d['F'],'b.-')
            pyplot.errorbar(d['L'],d['F'],d['Ferr'], fmt ='o')
            pyplot.semilogy()
            #
            min_L = num.floor(num.min(d['L']))
            max_L = num.ceil(num.max(d['L']))
            idx   = num.where(d['F'] > 0.)
            min_F = num.min(d['F'][idx])
            min_F = 10.**(num.round(num.log10(min_F)) - 1)
            max_F = num.max(d['F'][idx])
            max_F = 10.**(num.round(num.log10(max_F)) + 1)
            pyplot.axis([min_L,max_L,min_F,max_F])
            #
            pyplot.xlabel('L')
            pyplot.ylabel('|F|')
        fig = pyplot.gcf()
        self.fig = fig.number
        self.cursor = None
        if cursor == True:
            self.cursor = plotter.cursor(fig=self.fig,verbose=verbose)

    ##########################################################################
    def get_idx(self):
        """
        get point index from plot selection
        """
        if self.cursor == None:
            return None
        if self.cursor.clicked == False:
            return None
        L = self.cursor.x
        subplot = self.cursor.subplot
        if subplot < 0:
            return None
        hksets  = sort_data(self)
        idx = self._get_idx(subplot,L,hksets)
        return idx
    
    def _get_idx(self,subplot,L,hksets):
        d   = hksets[subplot]
        tmp = num.fabs(d['L']-L)
        idx = num.where(tmp==min(tmp))
        if len(idx) > 0:
            idx = idx[0]
        idx = tuple(d['idx'][idx][0])
        return idx
    
    ##########################################################################
    def plot_point(self,idx=None,fig=None):
        """
        plot the raw data for a selected point

        idx = point index.  if idx = None, then uses last cursor click
        fig = fig number
        """
        if idx == None:
            idx = self.get_idx()
            if idx == None: return None
        if len(idx) > 1:
            point = idx[1]
            idx = idx[0]
        else:
            point = 0
        data = self.scan[idx]
        if self.scan_type[idx] == 'image':
            self.scan[idx].image.plot(idx=point,fig=fig)
        else:
            # plot scan data
            pass
        
    ##########################################################################
    def write_HKL(self,fname = 'ctr.lst'):
        """
        dump data file
        """
        f = open(fname, 'w')
        header = "#idx %5s %5s %5s %7s %7s\n" % ('H','K','L','F','Ferr')
        f.write(header)
        for i in range(len(self.L)):
            if self.I[i] > 0:
                line = "%4i %3.2f %3.2f %6.3f %6.6g %6.6g\n" % (i,round(self.H[i]),
                                                            round(self.K[i]),
                                                            self.L[i],self.F[i],
                                                            self.Ferr[i])
                f.write(line)
        f.close()

##########################################################################
#def sort_data(H,K,L,F,Ferr,idx,hkdecimal=3):
def sort_data(ctr,hkdecimal=3):
    """
    return a dict of sorted data

    Assume H,K define a set with a range of L values
    All arrays should be of len npts. 

    """
    # round H and K to sepcified precision
    H = num.around(ctr.H,decimals=hkdecimal)
    K = num.around(ctr.K,decimals=hkdecimal)
    L = ctr.L
    F = ctr.F
    Ferr = ctr.Ferr
    idx  = ctr.scan_index
    npts = len(F)

    #find all unique sets
    hkvals = []
    for j in range(npts):
        s = (H[j],K[j]) 
        if s not in hkvals:
            hkvals.append(s)

    # sort the hkvals
    # and stick data in correct set
    hkvals.sort()
    nsets = len(hkvals)
    #d = {'H':[],'K':[],'L':[],'F':[],'Ferr':[],'idx':[]}
    #hkset  = [copy.copy(d) for j in range(nsets)]
    hkset = []
    for j in range(nsets):
        hkset.append({'H':[],'K':[],'L':[],'F':[],'Ferr':[],'idx':[]})

    for j in range(npts):
        s      = (H[j],K[j])
        setidx = hkvals.index(s)
        hkset[setidx]['H'].append(H[j])
        hkset[setidx]['K'].append(K[j])
        hkset[setidx]['L'].append(L[j])
        hkset[setidx]['F'].append(F[j])
        hkset[setidx]['Ferr'].append(Ferr[j])
        hkset[setidx]['idx'].append(idx[j])

    # make arrays num arrays
    for j in range(nsets):
        hkset[j]['H'] = num.array(hkset[j]['H'])
        hkset[j]['K'] = num.array(hkset[j]['K'])
        hkset[j]['L'] = num.array(hkset[j]['L'])
        hkset[j]['F'] = num.array(hkset[j]['F'])
        hkset[j]['Ferr'] = num.array(hkset[j]['Ferr'])
        hkset[j]['idx']  = num.array(hkset[j]['idx'])

    # now sort each set by L
    for j in range(nsets):
        lidx = num.argsort(hkset[j]['L'])
        hkset[j]['H'] = hkset[j]['H'][lidx]
        hkset[j]['K'] = hkset[j]['K'][lidx]
        hkset[j]['L'] = hkset[j]['L'][lidx]
        hkset[j]['F'] = hkset[j]['F'][lidx]
        hkset[j]['Ferr'] = hkset[j]['Ferr'][lidx]
        hkset[j]['idx'] = hkset[j]['idx'][lidx]

    return hkset

##############################################################################
def image_point_F(scan,point,I='I_c',Inorm='Io',Ierr='Ierr_c',corr_params={}):
    """
    compute F for a single scan point in an image scan
    """
    d = {'I':0.0,'Inorm':0.0,'Ierr':0.0,'ctot':1.0,'F':0.0,'Ferr':0.0}
    d['I']     = scan[I][point]
    d['Inorm'] = scan[Inorm][point]
    d['Ierr']  = scan[Ierr][point]
    if corr_params == None:
        d['ctot'] = 1.0
        scale = 1.0
    else:
        # compute correction factors
        geom   = corr_params.get('geom')
        if geom == None: geom='psic'
        beam   = corr_params.get('beam_slits',{})
        det    = corr_params.get('det_slits')
        sample = corr_params.get('sample')
        scale  = corr_params.get('scale',1.0)
        scale  = float(scale)
        # get gonio instance for corrections
        if geom == 'psic':
            gonio = gonio_psic.psic_from_spec(scan['G'])
            _update_psic_angles(gonio,scan,point)
            corr  = CtrCorrectionPsic(gonio=gonio,beam_slits=beam,
                                      det_slits=det,sample=sample)
            d['ctot']  = corr.ctot_stationary()
        else:
            print "Geometry %s not implemented" % geom
            ctot = 1.0
    # compute F
    if d['I'] <= 0.0 or d['Inorm'] <= 0.:
        d['F']    = 0.0
        d['Ferr'] = 0.0
    else:
        yn     = scale*d['I']/d['Inorm']
        yn_err = yn * num.sqrt( (d['Ierr']/d['I'])**2. + 1./d['Inorm'] )
        d['F']    = num.sqrt(d['ctot']*yn)
        d['Ferr'] = num.sqrt(d['ctot']*yn_err)
    
    return d

##############################################################################
def _update_psic_angles(gonio,scan,point):
    """
    given a psic gonio instance, a scandata object
    and a scan point, update the gonio angles...
    """
    npts = int(scan.dims[0])
    if len(scan['phi']) == npts:
        phi=scan['phi'][point]
    else:
        phi=scan['phi']
    if len(scan['chi']) == npts:
        chi=scan['chi'][point]
    else:
        chi=scan['chi']
    if len(scan['eta']) == npts:
        eta=scan['eta'][point]
    else:
        eta=scan['eta']
    if len(scan['mu']) == npts:
        mu=scan['mu'][point]
    else:
        mu=scan['mu']
    if len(scan['nu']) == npts:
        nu=scan['nu'][point]
    else:
        nu=scan['nu']
    if len(scan['del']) == npts:
        delta=scan['del'][point]
    else:
        delta=scan['del']
    #
    gonio.set_angles(phi=phi,chi=chi,eta=eta,
                     mu=mu,nu=nu,delta=delta)

##############################################################################
class CtrCorrectionPsic:
    """
    Data point operations / corrections for Psic geometry

    Note: All correction factors are defined such that the
    measured data is corrected by multiplying times
    the correction: 
      Ic  = Im*ct
    where
      Im = Idet/Io = uncorrected (measured) intensity

    In other words we use the following formalism:
      Im = (|F|**2)* prod_i(Xi)
    where Xi are various (geometric) factors that 
    influence the measured intensity.  To get the
    structure factor:
      |F| = sqrt(Im/prod_i(Xi)) = sqrt(Im* ct)
    and
      ct = prod_i(1/Xi) = prod_i(ci)
      ci = 1/Xi
      
    If there is an error or problem in the routine for a sepcific
    correction factor, (e.g. divide by zero), the routine should
    return a zero.  This way the corrected data is zero'd....

    The correction factors depend on the goniometer geometry
     gonio = gonio_psic.Psic instance

    The slits settings are needed.  Note if using a large area detector
    you may pass det_slits = None and just spill off will be computed
       beam_slits = {'horz':.6,'vert':.8}
       det_slits = {'horz':20.0,'vert':10.5}
    these are defined wrt psic phi-frame:
       horz = beam/detector horz width (total slit width in lab-z,
              or the horizontal scattering plane)
       vert = detector vert hieght (total slit width in lab-x,
              or the vertical scattering plane)

    A sample description is needed.
    If sample = a number then is is taken as the diameter
    of a round sample mounted on center.

    Otherwise is may describe a general sample shape:    
      sample = {}
        sample['polygon'] = [[1.,1.], [.5,1.5], [-1.,1.],
                             [-1.,-1.],[0.,.5],[1.,-1.]]
        sample['angles']  = {'phi':108.0007,'chi':0.4831}

        polygon = [[x,y,z],[x,y,z],[x,y,z],....]
                  is a list of vectors that describe the shape of
                  the sample.  They should be given in general lab
                  frame coordinates.

         angles = {'phi':0.,'chi':0.,'eta':0.,'mu':0.}
             are the instrument angles at which the sample
             vectors were determined.

      The lab frame coordinate systems is defined such that:
        x is vertical (perpendicular, pointing to the ceiling of the hutch)
        y is directed along the incident beam path
        z make the system right handed and lies in the horizontal scattering plane
          (i.e. z is parallel to the phi axis)

        The center (0,0,0) of the lab frame is the rotation center of the instrument.

        If the sample vectors are given at the flat phi and chi values and with
        the correct sample hieght (sample Z set so the sample surface is on the
        rotation center), then the z values of the sample vectors will be zero.
        If 2D vectors are passed we therefore assume these are [x,y,0].  If this
        is the case then make sure:
            angles = {'phi':flatphi,'chi':flatchi,'eta':0.,'mu':0.}

        The easiest way to determine the sample coordinate vectors is to take a picture
        of the sample with a camera mounted such that is looks directly down the omega
        axis and the gonio angles set at the sample flat phi and chi values and
        eta = mu = 0. Then find the sample rotation center and measure the position
        of each corner (in mm) with up being the +x direction, and downstream
        being the +y direction.  

    Note need to add attenuation parameters.  
    
    """
    def __init__(self,gonio=None,beam_slits={},det_slits=None,sample=None):
        self.gonio      = gonio
        if self.gonio.calc_psuedo == False:
            self.gonio.calc_psuedo = True
            self.gonio._update_psuedo()
        self.beam_slits = beam_slits
        self.det_slits  = det_slits
        self.sample     = sample
        # fraction horz polarization
        self.fh         = 1.0

    ##########################################################################
    def ctot_stationary(self,plot=False):
        """
        correction factors for stationary measurements (e.g. images)
        """
        cp = self.polarization()
        cl = self.lorentz_stationary()
        ca = self.active_area(plot=plot)
        ct = (cp)*(cl)*(ca)
        if plot == True:
            print "Polarization=%f" % cp
            print "Lorentz=%f" % cl
            print "Area=%f" % ca
            print "Total=%f" % ct
        return ct

    ##########################################################################
    def lorentz_stationary(self):
        """
        Compute the Lorentz factor for a stationary (image)
        measurement.  See Vlieg 1997

        Measured data is corrected for Lorentz factor as: 
          Ic  = Im * cl
        """
        beta  = self.gonio.pangles['beta']
        cl = sind(beta)
        return cl

    ##########################################################################
    def lorentz_scan(self):
        """
        Compute the Lorentz factor for a generic scan
        Note this is approximate. In general for bulk xrd
        with single crystals lorentz factor is defined as:
          L = 1/sin(2theta)
        We need L for specific scan types, e.g. phi, omega, etc..
        See Vlieg 1997

        Measured data is corrected for Lorentz factor as: 
          Ic  = Im * cl = Im/L
        """
        tth  = self.gonio.pangles['tth']
        cl = sind(tth)
        return cl

    ##########################################################################
    def rod_intercept(self,):
        """
        Compute the dl of the rod intercepted by the detector.
        (this correction only applies for rocking scans)
        This can be (roughly) approximated from:
          dl = dl_o * cos(beta)
          where dl_o is the detector acceptance at beta = 0

        Note this is an approximation for all but simple specular scans,
        Should use the detector acceptance polygon and determine
        the range of dl for the specific scan axis used.
        
        Measured data is corrected for the intercept as: 
          Ic  = Im * cr = Im/dl
        """
        beta  = self.gonio.pangles['beta']
        cr   = cosd(beta)
        return cr
    
    ##########################################################################
    def polarization(self,):
        """
        Compute polarization correction factor.
        
        For a horizontally polarized beam (polarization vector
        parrallel to the lab-frame z direction) the polarization
        factor is normally defined as:
           p = 1-(cos(del)*sin(nu))^2
        For a beam with mixed horizontal and vertical polarization:
           p = fh( 1-(cos(del)*sin(nu))^2 ) + (1-fh)(1-sin(del)^2)
        where fh is the fraction of horizontal polarization.

        Measured data is corrected for polarization as: 
          Ic  = Im * cp = Im/p
        """
        fh    = self.fh
        delta = self.gonio.angles['delta']
        nu    = self.gonio.angles['nu']
        p = 1. - ( cosd(delta) * sind(nu) )**2.
        if fh != 1.0:
            p = fh * c_p + (1.-fh)*(1.0 - (sind(delta))**2.)
        if p == 0.:
            cp = 0.
        else:
            cp = 1./p

        return cp

    ##########################################################################
    def active_area(self,plot=False):
        """
        Compute active area correction (c_a = A_beam/A_int)
        Use to correct scattering data for area effects,
        including spilloff, i.e.
           Ic = Im * ca = Im/A_ratio 
           A_ratio = A_int/A_beam 
        where
           A_int = intersection area (area of beam on sample
                   viewed by detector)
           A_beam = total beam area
        """
        if self.beam_slits == {}:
            print "Warning beam slits not specified"
            return 1.0
        alpha = self.gonio.pangles['alpha']
        beta  = self.gonio.pangles['beta']
        if plot == True:
            print 'alpha = ', alpha, ', beta = ', beta
        if alpha < 0.0:
            print 'alpha is less than 0.0'
            return 0.0
        elif beta < 0.0:
            print 'beta is less than 0.0'
            return 0.0

        # get beam vectors
        bh = self.beam_slits['horz']
        bv = self.beam_slits['vert']
        beam = gonio_psic.beam_vectors(h=bh,v=bv)

        # get det vectors
        if self.det_slits == None:
            det = None
        else:
            dh = self.det_slits['horz']
            dv = self.det_slits['vert']
            det  = gonio_psic.det_vectors(h=dh,v=dv,
                                          nu=self.gonio.angles['nu'],
                                          delta=self.gonio.angles['delta'])
        # get sample poly
        if type(self.sample) == types.DictType:
            sample_vecs = self.sample['polygon']
            sample_angles = self.sample['angles']
            sample = gonio_psic.sample_vectors(sample_vecs,
                                               angles=sample_angles,
                                               gonio=self.gonio)
        else:
            sample = self.sample

        # compute active_area
        (A_beam,A_int) = active_area(self.gonio.nm,ki=self.gonio.ki,
                                     kr=self.gonio.kr,beam=beam,det=det,
                                     sample=sample,plot=plot)
        if A_int == 0.:
            ca = 0.
        else:
            ca = A_beam/A_int

        return ca

##############################################################################
##############################################################################
def test1():
    #psic = psic_from_spec(G,angles={})
    psic = gonio_psic.test2(show=False)
    psic.set_angles(phi=12.,chi=30.,eta=20.,
                    mu=25.,nu=75.,delta=20.)
    #print psic
    #
    beam_slits = {'horz':.6,'vert':.8}
    det_slits = {'horz':20.0,'vert':10.5}
    sample = {}
    sample['polygon'] = [[1.,1.], [.5,1.5], [-1.,1.], [-1.,-1.],[0.,.5],[1.,-1.]]
    sample['angles']  = {'phi':108.0007,'chi':0.4831}
    #
    cor = CtrCorrectionPsic(gonio=psic,beam_slits=beam_slits,
                            det_slits=det_slits,sample=sample)
    ct = cor.ctot_stationary(plot=True)

##########################################################################
if __name__ == "__main__":
    """
    test 
    """
    test1()
    #test2()


