# -*- coding: utf-8 -*-
"""Two-dimensional Fourier Transform Spectrum and its calculation


"""
from functools import partial
import numbers

import h5py
import matplotlib.pyplot as plt  
import numpy

from ..core.time import TimeAxis
from ..core.frequency import FrequencyAxis
from ..builders.aggregates import Aggregate
from ..builders.molecules import Molecule
from ..core.managers import eigenbasis_of
from ..core.managers import energy_units
from ..qm.propagators.poppropagator import PopulationPropagator 
from ..core.units import convert
from .. import COMPLEX

from ..utils import derived_type

import quantarhei as qr

import time

try:

    import aceto.nr3td as nr3td            
    from aceto.lab_settings import lab_settings
    from aceto.band_system import band_system            
    _have_aceto = True
    
except:
    #
    # FIXME: There should be an optional warning and a fall back onto
    # quantarhei.implementations.aceto module
    #
    #raise Exception("Aceto not available")
    #from ..implementations.aceto import nr3td            
    _have_aceto = False 


# FIXME: Check these names

#
#  Pathway types
#
_ptypes = ["R1g", "R2g", "R3g", "R4g", "R1fs", "R2fs", "R3fs", "R4fs"]

#
# Processes --- GSB, SE, ESA and DC
#
_processes = dict(GSB=[_ptypes[0], _ptypes[1]], SE=[_ptypes[2], _ptypes[3]],
                  ESA=[_ptypes[4], _ptypes[5]], DC=[_ptypes[6], _ptypes[7]])

#
# Types of signals --- rephasing (REPH), non-rephasing (NONR) 
#                      and double coherence (DC)
#
_signals = dict(REPH=[_ptypes[1], _ptypes[2], _ptypes[4]],
                NONR=[_ptypes[0], _ptypes[3], _ptypes[5]],
                DC=[_ptypes[6], _ptypes[7]])

#
# Storage resolutions
#
_resolutions = ["off", "signals", "processes", "types", "pathways"]


def _resolution2number(res):
    """Converts resolution string to number
    
    Parameters
    ----------
    
    res : string
        Resolution string. Here is conversion table    
        | string    | integer |
        | pathways  |   4     |
        | types     |   3     |
        | processes |   2     |
        | signals   |   1     |
        | off       |   0     |
    
    
    >>> _resolution2number("pathways")
    4
    
    >>> _resolution2number("types")
    3
    
    >>> _resolution2number("processes")
    2
    
    >>> _resolution2number("signals")
    1
    
    >>> _resolution2number("off")
    0
    
    
    
    """
    if res in _resolutions:
        return _resolutions.index(res)
    else:
        raise Exception("Unknow resolution level in TwoDSpectrum")


def _get_type_and_tag(obj, storage):

    if obj.current_dtype not in _ptypes:
        # check the current_type attribute
        raise Exception("Wrong pathways type")

    try:
        # get the dictionary of pathways with a give type
        piece = storage[obj.current_dtype]
    except IndexError:
        # if it does not exist, create it
        storage[obj.current_dtype] = {}
        piece = storage[obj.current_dtype]

    if obj.current_tag in piece.keys():
        # if the tag exists raise Exception
        raise Exception("Tag already exists")
        
    return piece


def _pathways_to_processes(obj, process):

    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    else:
        return numpy.zeros((1,1), dtype=COMPLEX)
        
    if process not in _processes:
        raise Exception("Unknown process: "+process)
        
    else:
        
        # types corresponding to process
        types = _processes[process]
        for typ in types:
            # pways corresponding to a given type
            try:
                pways = obj._d__data[typ]
            except:
                pways = []
            # sum those pathways
            for tag in pways:
                data += pways[tag]
        
    return data


def _pathways_to_signals(obj, signal):

    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)
        
    if signal not in _signals:
        raise Exception("Unknown signal: "+signal)
        
    else:
        
        # types corresponding to signal
        types = _signals[signal]
        for typ in types:
            # pways corresponding to a given type
            try:
                pways = obj._d__data[typ]
            except:
                pways = []
            # sum those pathways
            for tag in pways:
                data += pways[tag]
        
    return data        


def _pathways_to_total(obj):
    
    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)

    for signal in _signals:
        
        data += _pathways_to_signals(obj, signal)

    return data        


def _types_to_processes(obj, process):
    """Sums pathways of different types into a specified process spectrum
    
    
    """
    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)


    types = _processes[process]
    for dtype in types:
        try:
            ddata = obj._d__data[dtype]
        except KeyError:
            # set to None if dtype not present
            ddata = None
        except AttributeError:
            # no data
            ddata = None
            
        if ddata is not None:
            data += ddata

    return data


def _types_to_signals(obj, signal):
    """Sums pathways of different types into a specified signal spectrum
    
    
    """
    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)
        
    types = _signals[signal]
    
    for dtype in types:
        try:
            ddata = obj._d__data[dtype]
        except KeyError:
            # set to None if dtype not present
            ddata = None
        except AttributeError:
            # no data
            ddata = None
            
        if ddata is not None:
            data += ddata

    return data


def _signals_to_total(obj):
    """Sums spectra corresponding to different signals into the total spectrum
    
    """    
    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    
        for signal in _signals:
            
            data += obj._d__data[signal]
            
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)

    return data
            

def _processes_to_total(obj):
    """Sums spectra corresponding to different processes into the total spectrum
    
    """
    
    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    
        for process in _processes:
            
            data += obj._d__data[process]
            
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)

    return data


def _types_to_total(obj):
    """Sums all pathways into the total spectrum
    
    
    """
    if obj.storage_initialized:
        data = numpy.zeros((obj.xaxis.length,
                            obj.yaxis.length),
                            dtype=COMPLEX)
    
        # sum over all processes
        for process in _processes:
            
            data += _types_to_processes(process)
            
    else:
        data = numpy.zeros((1,1), dtype=COMPLEX)

    return data


def twodspectrum_dictionary(name, dtype):
    """Defines operations on the storage of two-dimensional spectral data
    
    
    """
    
    storage_name = '_'+name

    @property
    def prop(self):
        
        storage = getattr(self, storage_name)
        
        #
        # with pathway resolution => type and tag has to be specified
        #
        if self.storage_resolution == "pathways":
             
            if self.current_dtype in _ptypes:

                if self.storage_initialized:
    
                    try:
                        piece = storage[self.current_dtype]
                    except:
                        return numpy.zeros((self.xaxis.length,
                                            self.yaxis.length),
                                            dtype=COMPLEX)

                else:
                    return numpy.zeros((1,1), dtype=COMPLEX)
                                
                #
                # return as pathway
                #
                if self.current_tag is not None:
                    return piece[self.current_tag]
            
                #
                # return as type
                #
                else:
                    # tag not specified so we add up all pathways
                    # of a given type
                    k_i = 0
                    for tag in piece:
                        dat = piece[tag]
                        if k_i == 0:
                            data = dat.copy()
                        else:
                            data += dat
                        k_i += 1
                            
                    return data
                    
            elif self.current_dtype in _processes:
                
                #
                # return as process
                #
                return _pathways_to_processes(self, self.current_dtype)
                
            elif self.current_dtype in _signals:
                #
                # return as signals
                #
                return _pathways_to_signals(self, self.current_dtype)
                
            elif self.current_dtype == "total":
                
                #
                # return total spectrum
                #
                return _pathways_to_total(self)
 
        #
        # Resolution = "types"
        #
        elif self.storage_resolution == "types":
            
            if self.current_dtype in _ptypes:
                return storage[self.current_dtype]

            elif self.current_dtype in _processes:
                
                # return as process
                return _types_to_processes(self, self.current_dtype)
            
            elif self.current_dtype in _signals:
                #
                # return as signals
                #
                return _types_to_signals(self, self.current_dtype)
                
            elif self.current_dtype == "total":
                
                #
                # return total spectrum
                #
                return _types_to_total(self)

        #
        # Resolution = "processes"
        #
        elif self.storage_resolution == "processes":

            if self.current_dtype in _processes:
                return storage[self.current_dtype]
            
            elif self.current_dtype == "total":
                
                #
                # Return total spectrum
                #
                return _processes_to_total(self)

        #
        # Resolution = "signals"
        #
        elif self.storage_resolution == "signals":

            if self.current_dtype in _signals:
                return storage[self.current_dtype]
            
            elif self.current_dtype == "total":
                
                #
                # return total spectrum
                #
                return _signals_to_total(self)                
                
            
        else:
            raise Exception("not implemented")              

        
    @prop.setter
    def prop(self, value):
        
        ini = getattr(self, "storage_initialized")
        if not ini:
            setattr(self, storage_name, {})
            setattr(self, "storage_initialized", True)
        
        if isinstance(value, numpy.ndarray):

            storage = getattr(self, storage_name)

            #
            # with pathway resolution => type and tag has to be specified
            #
            if self.storage_resolution == "pathways":

                if self.current_dtype not in _ptypes:
                    # check the current_type attribute
                    raise Exception("Wrong pathways type")
            
                try:
                    # get the dictionary of pathways with a give type
                    piece = storage[self.current_dtype]
                except KeyError:
                    # if it does not exist, create it
                    storage[self.current_dtype] = {}
                    piece = storage[self.current_dtype]
            
                if self.current_tag in piece.keys():
                    # if the tag exists raise Exception
                    raise Exception("Tag already exists")
                        
                    if value.shape != (self.xaxis.length, self.yaxis.length):
                        # if the data shape is not consistent, raise Exception
                        raise Exception("Data not consistent with spectrum axes")

                piece[self.current_tag] = value
                                        
        else:
            raise TypeError('{} must contain \
                            values of type {})'.format(name, dtype), dtype)
            
    return prop

#
# Storage type for 2D spectra
#
TwoDSpectrumDataArray = partial(twodspectrum_dictionary, dtype=numbers.Complex)     


class TwoDSpectrumBase:
    """Basic class of a two-dimensional spectrum
    
    
    """
    
    # spectral types
    stypes = ["rephasing", "non-rephasing", "nonrephasing", "total"]
    
    # spectral parts
    sparts = ["real", "imaginary"]
    
    # to keep Liouville pathways separate?
    keep_pathways = False
    
    dtypes = ["Tot", "Reph", "Nonr"]
    
    # to keep stypes separate?
    keep_stypes = True

    #
    # Storage of 2D data
    #
    d__data = TwoDSpectrumDataArray("d__data")


    def __init__(self):
        super().__init__()
        
        self.xaxis = None
        self.yaxis = None
            
        self.reph2D = None
        self.nonr2D = None
        self.data = None
        
        self.dtype = None
        
        # initially, the highest possible resolution is set
        self.storage_resolution = "pathways"
        self.storage_initialized = False
        
        self.current_dtype = None
        self.current_tag = None
        self.address_length = 1


    def set_axis_1(self, axis):
        """Sets the x-axis of te spectrum (omega_1 axis)
        
        """
        self.xaxis = axis


    def set_axis_3(self, axis):
        """Sets the y-axis of te spectrum (omega_3 axis)
        
        """
        self.yaxis = axis


    def set_data_type(self, dtype="Tot"):
        """Sets the data type for this 2D spectrum
        
        Parameters
        ----------
        
        dtype : string
           Specifies the type of data stored in this TwoDSpectrum object 
        """
        
        if dtype in self.dtypes:
            self.dtype = dtype
        else:
            raise Exception("Unknown data type for TwoDSpectrum object")

        
    def set_data(self, data, dtype="Tot"):
        """Sets the data of the 2D spectrum
        
        Sets the object data depending on the specified type and stores the
        type
        
        
        Parameters
        ----------
        
        data : 2D array
            Data of the spectrum, float or complex
            
        dtype : string
            Type of the data stored. Three values are allowed, namely, `Reph`
            for rephasing spectra, `Nonr` for non-rephasing spectra, and `Tot` 
            for total spectrum, which is the sum of both
            
        """
        if self.dtype is None:
            if dtype in self.dtypes:
                self.dtype = dtype
        else:
            if dtype != self.dtype:
                raise Exception("Incorrect data type in TwoDSpectrum")
                
        if dtype == "Tot":
            self.data = data
            
        elif dtype == "Reph":
            self.reph2D = data
            
        elif dtype == "Nonr":        
            self.nonr2D = data
            
        else:
            
            raise Exception("Unknow type of data: "+dtype)


    def add_data(self, data, dtype="Tot"):
        
        if dtype is None:
            if dtype in self.dtypes:
                self.dtype = dtype
        else:
            if dtype != self.dtype:
                raise Exception("Incorrect data type in TwoDSpectrum")

        if dtype == "Tot":
            
            if self.data is None:
                self.data = numpy.zeros(data.shape, dtype=data.dtype)
            self.data += data
            
        elif dtype == "Reph":
            if self.reph2D is None:
                self.reph2D = numpy.zeros(data.shape, dtype=data.dtype)
            self.reph2D += data                
            
        elif dtype == "Nonr":
            if self.nonr2D is None:
                self.nonr2D = numpy.zeros(data.shape, dtype=data.dtype)                
            self.nonr2D += data

        else:
            
            raise Exception("Unknow type of data: "+dtype)


    def set_data_flag(self, flag):
        """Sets a flag by which date will be retrieved and save to `data`
        attribute
        
        
        """
        
        if isinstance(flag, list):
            self.current_dtype = flag[0]
            try:
                self.current_tag = flag[1]
            except IndexError:
                raise Exception("flag in form of a list must have"
                                +" two elements")
            self.address_length = 2
        else:
            self.current_dtype = flag
            self.current_tag = None
            self.address_length = 1


    def get_all_tags(self):
        """Retunrs tags of the pathways stored under `pathways` resolution
        
        The tags are returned in a two membered list with its type, i.e.
        as [type, tag]
        
        """
        tags = []
        for typ in _ptypes:
            try:
                pdict = self._d__data[typ]
            except KeyError:
                pdict = {}
            keys = pdict.keys()
            for key in keys:
                tags.append([typ, key])
                
        return tags


    def set_resolution(self, resolution):
        """Sets the storage resolution attribute of TwoDSpectrum


        Parameters
        ----------
        
        resolution : string
            Resolution in which data are stored in TwoDSpectrum object.
            Values are one of the strings: `pathways` - stores individual
            Liouville pathways, `types` - stores sets of pathways corresponding
            to different shapes of Feynman diagrams, `processes` - stores
            data corresponding to processes, such as stimulated emission and
            ground state bleach, `signals` - stores only rephasing and
            non-rephasing signals separately, `off` - stores only total
            spectrum.
            
        
        Examples
        --------
        
        Initial resolution is the highest one, i.e. 'pathways'
        
        >>> spect1 = TwoDSpectrum()
        >>> spect2 = TwoDSpectrum()
        >>> spect1.storage_resolution
        'pathways'
        
        We can set only decreasing resolution
        
        >>> spect1.set_resolution("types")
        >>> spect2.set_resolution("types")
        >>> spect1.storage_resolution
        'types'

        "types" can be converted either to "processes" or "signals"
        
        >>> spect1.set_resolution("processes")
        >>> spect1.storage_resolution
        'processes'

        "processes" cannot be converted to "signals"

        >>> spect1.set_resolution("signals")
        Traceback (most recent call last):
            ...
        Exception: Cannot convert resolution for level 2 to level 1
                
        >>> spect2.set_resolution("signals")
        >>> spect2.storage_resolution
        'signals'
        
        If we set increasing resolution we get an exception
        
        >>> spect1.set_resolution("types")
        Traceback (most recent call last):
            ...
        Exception: Cannot convert from lower to higher resolution

        From "signals" and "types" you can convert to no resolution, i.e.
        to total spectrum where storage resolution is 'off'

        >>> spect1.set_resolution("off")
        >>> spect1.storage_resolution
        'off'
        
        >>> spect2.set_resolution("off")
        >>> spect2.storage_resolution
        'off'
        
        """
        if resolution in _resolutions:
            res_old = _resolution2number(self.storage_resolution)
            res_new = _resolution2number(resolution)
            if res_old < res_new:
                raise Exception("Cannot convert from lower"+
                                " to higher resolution")
            elif res_old > res_new:
                # recalculate data towards lower resolution
                self._convert_resolution(res_old, res_new)
            
            self.storage_resolution = resolution
        else:
            raise Exception("Unknown resolution: "+resolution)


    def _convert_resolution(self, old, new):
        """Converts storage from one level of resolution to another
        
        """
        
        # convert "pathways" to "types"
        if (old == 4) and (new == 3):
            
            storage = {}
            data_present = True
            
            for dtype in _ptypes:
                # get a dictionary of pathways of a given type
                try:
                    pdict = self._d__data[dtype]
                except KeyError:
                    # ignore if some are absent
                    pdict = {}                    
                except AttributeError:
                    # no data
                    pdict = {}
                    data_present = False

                # sum all data
                if data_present:
                    data = numpy.zeros((self.xaxis.length, self.yaxis.length),
                                       dtype=COMPLEX)
                else:
                    data = numpy.zeros((1, 1),
                                       dtype=COMPLEX)
                    
                for key in pdict.keys():
                    data += pdict[key]
                
                storage[dtype] = data
           
            self._d__data = storage
                  
        # convert "types" to "processes"
        elif (old == 3) and (new == 2):
            
            storage = {}
            
            for process in _processes.keys():
                
                data = _types_to_processes(self, process)                    
                storage[process] = data
           
            self._d__data = storage
            
        # convert "types" to "signals"
        elif (old == 3) and (new == 1):

            storage = {}
            
            for signal in _signals.keys():
                
                data = _types_to_signals(self, signal) 
                storage[signal] = data
           
            self._d__data = storage
            
        # converts "signals" to "off"
        elif (old == 1) and (new == 0):
            storage = {}
            
            data = _signals_to_total(self)
            storage["off"] = data
        
        # converts "processes" to "off"
        elif (old == 2) and (new == 0):
            storage = {}
            
            data = _processes_to_total(self)
            storage["off"] = data
            
        else:
            raise Exception("Cannot convert resolution for level "+str(old)+
                            " to level "+str(new))


    def _add_data(self, data, resolution=None, dtype="Tot", tag=None):
        """Adds data to this 2D spectrum
        
        This method is used when partial data are stored in this spectrum
        object, and it is expected that more data will come. To set spectrum
        data in one shot, you can use `set_data` method.
        
        
        Parameters
        ----------
        
        data : array
            Numpy array compatible in dimensions with the axes of the spectrum
            
        resolution : string or None
            Resolution of adding data. If the data correspond to individual
            `pathways` (resolution="pathways"), a `types` of pathways
            (resolution="types") such as "R1g", "R2g" etc., 
            `process` (resolution="processes") such as "GSB", "ESA" etc.,
            or `signals` such as "Reph" or "Nonr" (resolution="signals"). 
            One can also store a complete spectrum under the resolution="off".
            
        dtype : string
            Type of data; under resolution="pathway", dtype specifies the 
            character of the pathway (such as "R1g", "R2g", etc.)
            
        tag : string
            Used in the resolution="pathway". It provides a unique tag to 
            identify the pathway
            
        """
        if resolution is None:
            resolution = self.storage_resolution
        else:
            res1 = _resolution2number(resolution)
            res2 = _resolution2number(self.storage_resolution)
            if res1 <= res2:
            
                pass
            
            else:
                raise Exception("This TwoDSpectrum does not have enough "
                                +"resolution to add data with resolution = "
                                +resolution)

        if resolution == "pathways":
            if dtype in _ptypes:
                if tag is not None:
                    self.set_data_flag([dtype, tag])
                    self.d__data = data
                else:
                    raise Exception("Tag for Liouville pathway not specified")
            else:
                raise Exception("Unknown type of Liouville pathway: "+dtype)
        

    def _set_data(self, data, mode=None, dtype="Tot", tag=None):
        pass

    
class TwoDSpectrum(TwoDSpectrumBase):
    """This class represents a single 2D spectrum
    
    Methods
    -------
    
    plot(fig=None, window=None, stype="total", spart="real",
         vmax=None, vmin_ratio=0.5, 
         colorbar=True, colorbar_loc="right",
         cmap=None, Npos_contours=10,
         show_states=None,
         text_loc=[0.05,0.9], fontsize="20", label=None)
    
    
    """
    
    def __init__(self, keep_pathways=False, keep_stypes=True):
        self.keep_pathways = keep_pathways
        self.keep_stypes = keep_stypes
        self.t2 = -1.0
        super().__init__()


    def set_t2(self, t2):
        """Sets the t2 (waiting time) of the spectrum
        
        
        """
        self.t2 = t2


    def get_t2(self):
        """Returns the t2 (waiting time) of the spectrum
        
        """
        return self.t2
    
    
    def get_value_at(self, x, y):
        """Returns value of the spectrum at a given coordinate
        
        """
        if self.dtype is None:
            raise Exception("No data in the TwoDSpectrum object")
            
        (ix, dist) = self.xaxis.locate(x)
        (iy, dist) = self.yaxis.locate(y)    
        
        if self.dtype == "Tot":
            return self.data[ix,iy]
            #return numpy.real(self.reph2D[ix,iy]+self.nonr2D[ix,iy])
        elif self.dtype == "Reph":
            return self.reph2D[ix,iy]
        elif self.dtype == "Nonr":
            return self.nonr2D[ix,iy]

    
    def get_max_value(self):
        
        return numpy.amax(numpy.real(self.reph2D+self.nonr2D))
            
    
    def devide_by(self, val):
        """Devides the total spectrum by a value
        
        """
        self.reph2D = self.reph2D/val
        self.nonr2D = self.nonr2D/val  


    def get_PumpProbeSpectrum(self):
        """Returns a PumpProbeSpectrum corresponding to the 2D spectrum
        
        """
        from .pumpprobe import PumpProbeSpectrumCalculator
        ppc = PumpProbeSpectrumCalculator()
        return ppc.calculate_from_2D(self)
    
    
    def plot(self, fig=None, window=None, stype="total", spart="real",
             vmax=None, vmin_ratio=0.5, 
             colorbar=True, colorbar_loc="right",
             cmap=None, Npos_contours=10,
             show_states=None,
             text_loc=[0.05,0.9], fontsize="20", label=None):
        """Plots the 2D spectrum
        
        Parameters
        ----------
        
        fig : matplotlib.figure
            Figure into which plotting will be done. This is used e.g. when
            making a movie using moview writter (may be obsolete)
            
        window : list
            Specifies the plotted window in current energy units. When axes
            are x and y, the window is specified as window=[x_min,x_max,y_min,y_max]
            
        stype : {"total", "rephasing", "non-rephasing"}
            type of the spectrum 
            
            
        """
        
        if stype == "total":
            if (self.reph2D is not None) and (self.nonr2D is not None):
                spect2D = self.reph2D + self.nonr2D 
            elif self.reph2D is not None:
                spect2D = self.reph2D 
            elif self.nonr2D is not None:
                spect2D = self.nonr2D
                
            
        elif stype == "rephasing":
            spect2D = self.reph2D
        elif stype == "non-rephasing":
            spect2D = self.nonr2D            
        else:
            raise Exception("Undefined spectrum type"+stype)
        
        if spart == "real":
            spect2D = numpy.real(spect2D)
        elif spart == "imaginary":
            spect2D = numpy.imag(spect2D)
        elif spart == "abs":
            spect2D = numpy.abs(spect2D)
        else:
            raise Exception("Undefined part of the spectrum: "+spart)
         
            
        if window is not None: 
            axis = window
            w1_min = axis[0]
            w1_max = axis[1]
            w3_min = axis[2]
            w3_max = axis[3]

            (i1_min, dist) = self.xaxis.locate(w1_min)
            (i1_max, dist) = self.xaxis.locate(w1_max)

            (i3_min, dist) = self.yaxis.locate(w3_min)
            (i3_max, dist) = self.yaxis.locate(w3_max)   
            
        else:
            i1_min = 0
            i1_max = self.xaxis.length
            i3_min = 0
            i3_max = self.yaxis.length
            
    
        #
        # Plotting with given units on axes
        #
  
        realout = spect2D[i3_min:i3_max,i1_min:i1_max]
    
        if fig is None:
            fig, ax = plt.subplots(1,1)
        else:
            fig.clear()
            fig.add_subplot(1,1,1)
            ax = fig.axes[0]
            
        if cmap is None:
            cmap = plt.cm.rainbow
            
        if vmax is None:
            vmax = numpy.amax(realout)

        vmin = numpy.amin(realout)
        if vmin < -vmax*vmin_ratio:
            vmax = -vmin
        else:
            vmin = -vmax*vmin_ratio
        
        Npos = Npos_contours
        poslevels = [i*vmax/Npos for i in range(1, Npos)]
        neglevels = [-i*vmax/Npos for i in range(Npos,1,-1)]
        
        levo = self.xaxis.data[i1_min]
        prvo = self.xaxis.data[i1_max-1]
        dole = self.yaxis.data[i3_min]
        hore = self.yaxis.data[i3_max-1]
        
        cm = plt.imshow(realout, extent=[self.xaxis.data[i1_min],
                                    self.xaxis.data[i1_max-1],
                                    self.yaxis.data[i3_min],
                                    self.yaxis.data[i3_max-1]],
                   origin='lower', vmax=vmax, vmin=vmin,
                   interpolation='bilinear', cmap=cmap)  
        
        pos = text_loc
        
        # text
        if label is not None:
            label = label    
            ax.text((prvo-levo)*pos[0]+levo,
                (hore-dole)*pos[1]+dole,
                label,
                fontsize=str(fontsize))
        
        # positive contours
        plt.contour(self.xaxis.data[i1_min:i1_max],
                     self.yaxis.data[i3_min:i3_max],
                     realout, levels=poslevels, colors="k",
                     linewidth=1)
        
        # zero contour
        plt.contour(self.xaxis.data[i1_min:i1_max],
                     self.yaxis.data[i3_min:i3_max],
                     realout, levels=[0],colors="b",
                     linewidth=1)
        
        # negatove contours
        plt.contour(self.xaxis.data[i1_min:i1_max],
                     self.yaxis.data[i3_min:i3_max],
                     realout, levels=neglevels,colors="k",
                     linewidth=1)  
        
        
        if colorbar:
            plt.clim(vmin=vmin,vmax=vmax)
            fig.colorbar(cm)
            
        if show_states is not None:
            for en in show_states:  
                plt.plot([en,en],[dole,hore],'--k',linewidth=1.0)
                plt.plot([levo,prvo],[en,en],'--k',linewidth=1.0)
            

    def trim_to(self, window=None):
        """Trims the 2D spectrum to a specified region
        
        """
        if window is not None:
            axis = window
            w1_min = axis[0]
            w1_max = axis[1]
            w3_min = axis[2]
            w3_max = axis[3]

            (i1_min, dist) = self.xaxis.locate(w1_min)
            (i1_max, dist) = self.xaxis.locate(w1_max)

            (i3_min, dist) = self.yaxis.locate(w3_min)
            (i3_max, dist) = self.yaxis.locate(w3_max)    
            
            # create minimal off-set
            i1_min -=1
            i1_max +=1
            i3_min -=1
            i3_max +=1
            
            # reconstruct xaxis
            start_1 = self.xaxis.data[i1_min]
            length_1 = i1_max - i1_min
            step_1 = self.xaxis.step
            xaxis = FrequencyAxis(start_1,length_1,step_1, 
                                  atype=self.xaxis.atype,
                                  time_start=self.xaxis.time_start)
            self.xaxis = xaxis
            
            # reconstruct yaxis
            start_3 = self.yaxis.data[i3_min]
            length_3 = i3_max - i3_min
            step_3 = self.yaxis.step
            yaxis = FrequencyAxis(start_3,length_3,step_3, 
                                  atype=self.yaxis.atype,
                                  time_start=self.yaxis.time_start)                
            self.yaxis = yaxis            
            

            # reconstruct data
            if self.keep_stypes:
                if self.reph2D is not None:
                    reph2D = self.reph2D[i1_min:i1_max,i3_min:i3_max]
                    self.reph2D = reph2D  
                if self.nonr2D is not None:
                    nonr2D = self.nonr2D[i1_min:i1_max,i3_min:i3_max]
                    self.nonr2D = nonr2D 
                
            else:
                if self.data is not None:
                    data = self.data[i1_min:i1_max,i3_min:i3_max]
                    self.data = data
                
        else:
            # some automatic trimming in the future
            pass
                
    def show(self):
        
        plt.show()


    def savefig(self, filename):
        
        plt.savefig(filename)

 
    def _create_root_group(self, start, name):
        return start.create_group(name)
    
    def _save_attributes(self,rt):
        rt.attrs.create("t2", self.t2)
        keeps = []
        if self.keep_pathways:
            keeps.append(1)
        else:
            keeps.append(0)
        if self.keep_stypes:
            keeps.append(1)
        else:
            keeps.append(0)
            
        rt.attrs.create("keeps",keeps)

    def _load_attributes(self,rt):
        self.t2 = rt.attrs["t2"]
        keeps = rt.attrs["keeps"]
        self.keep_pathways = (keeps[0] == 1)
        self.keep_stypes = (keeps[1] == 1)
                    
    def _save_data(self,rt):
        if self.keep_stypes:
            rt.create_dataset("reph2D",data=self.reph2D)
            rt.create_dataset("nonr2D",data=self.nonr2D)
        else:
            rt.create_dataset("data",data=self.data)

    def _load_data(self,rt):
        if self.keep_stypes:
            self.reph2D = numpy.array(rt["reph2D"])
            self.nonr2D = numpy.array(rt["nonr2D"])
        else:
            self.data = numpy.array(rt["data"]) 
            
    def _save_axis(self, rt, name, ax):
        axdir = rt.create_group(name)
        axdir.attrs.create("start",ax.start)
        axdir.attrs.create("length",ax.length)
        axdir.attrs.create("step",ax.step)
        #FIXME: atype and time_start

    def _load_axis(self, rt, name):
        axdir = rt[name]
        start = axdir.attrs["start"]
        length = axdir.attrs["length"]
        step = axdir.attrs["step"]
        return FrequencyAxis(start, length, step)   
    
    def save(self, filename, units="int"):
        """Saves the whole object into file
        
        
        """
        with h5py.File(filename,"w") as f:
            rt = self._create_root_group(f,"spectrum")
            self._save_attributes(rt)
            self._save_data(rt)
            with energy_units(units):
                self._save_axis(rt, "xaxis", self.xaxis)
                self._save_axis(rt, "yaxis", self.yaxis)
            
            
            
    def load(self, filename, units="int"):
        """Loads the whole object from a file
        
        
        """
        with h5py.File(filename,"r") as f:
            rt = f["spectrum"]
            self._load_attributes(rt)
            self._load_data(rt)
            with energy_units(units):
                self.xaxis = self._load_axis(rt, "xaxis")
                self.yaxis = self._load_axis(rt, "yaxis")    
                

class TwoDSpectrumCalculator:
    """Calculator of the 2D spectrum
    
    
    Enables setting up parameters of 2D spectrum calculation for later
    evaluation. The method `calculate` returns TwoDSpectrumContainer
    with a 2D spectrum.
    
    Parameters
    ----------
    
    
    """

    t1axis = derived_type("t1axis",TimeAxis)
    t2axis = derived_type("t2axis",TimeAxis)
    t3axis = derived_type("t3axis",TimeAxis)
    
    system = derived_type("system",[Molecule,Aggregate])
    
    def __init__(self, t1axis, t2axis, t3axis,
                 system=None,
                 dynamics="secular",
                 relaxation_tensor=None,
                 rate_matrix=None,
                 effective_hamiltonian=None):
            
            
        self.t1axis = t1axis
        self.t2axis = t2axis
        self.t3axis = t3axis
        
        #FIXME: check the compatibility of the axes 
        
        if system is not None:
            self.system = system
        
        #FIXME: properties to be protected
        self.dynamics = dynamics
        
        # unprotected properties
        self.data = None
        
        self._relaxation_tensor = None
        self._rate_matrix = None
        self._relaxation_hamiltonian = None
        self._has_relaxation_tensor = False
        if relaxation_tensor is not None:
            self._relaxation_tensor = relaxation_tensor
            self._has_relaxation_tensor = True
        if effective_hamiltonian is not None:
            self._relaxation_hamiltonian = effective_hamiltonian
        if rate_matrix is not None:
            self._rate_matrix = rate_matrix
            self._has_rate_matrix = True
            
        #self._have_aceto = False
        
        # after bootstrap information
        self.sys = None
        self.lab = None
        self.t1s = None
        self.t3s = None
        self.rmin = None
        self.rwa = None
        self.oa1 = None
        self.oa3 = None
        self.Uee = None
        self.Uc0 = None
        
        self.tc = 0
        
       
    def _vprint(self, string):
        """Prints a string if the self.verbose attribute is True
        
        """
        if self.verbose:
            print(string)
            
    def bootstrap(self,rwa=0.0, lab=None, verbose=False):
        """Sets up the environment for 2D calculation
        
        """


        self.verbose = verbose
    
    
        if True:
            
            # calculate 2D spectrum using aceto library

            ###############################################################################
            #
            # Create band_system from quantarhei classes
            #
            ###############################################################################
            
            if isinstance(self.system, Aggregate):
            
                pass
            
            else:
                
                raise Exception("Molecule 2D not implememted")
                
            agg = self.system
            
            #
            # hamiltonian and transition dipole moment operators
            #
            H = agg.get_Hamiltonian()
            D = agg.get_TransitionDipoleMoment()
            
            #
            # Construct band_system object
            #
            Nb = 3
            Ns = numpy.zeros(Nb, dtype=numpy.int)
            Ns[0] = 1
            Ns[1] = agg.nmono
            Ns[2] = Ns[1]*(Ns[1]-1)/2
            self.sys = band_system(Nb, Ns)
            
            
            #
            # Set energies
            #
            en = numpy.zeros(self.sys.Ne, dtype=numpy.float64)
            #if True:
            with eigenbasis_of(H):
                for i in range(self.sys.Ne):
                    en[i] = H.data[i,i]
                self.sys.set_energies(en)
            
                #
                # Set transition dipole moments
                #
                dge_wr = D.data[0:Ns[0],Ns[0]:Ns[0]+Ns[1],:]
                def_wr = D.data[Ns[0]:Ns[0]+Ns[1],
                                (Ns[0]+Ns[1]):(Ns[0]+Ns[1]+Ns[2]),:]
            
                dge = numpy.zeros((3,Ns[0],Ns[1]), dtype=numpy.float64)
                deff = numpy.zeros((3,Ns[1],Ns[2]), dtype=numpy.float64)
                
                for i in range(3):
                    dge[i,:,:] = dge_wr[:,:,i]
                    deff[i,:,:] = def_wr[:,:,i]
                self.sys.set_dipoles(0,1,dge)
                self.sys.set_dipoles(1,2,deff)
            
            
            #
            # Relaxation rates
            #
            KK = agg.get_RedfieldRateMatrix()
            
            # relaxation rate in single exciton band
            Kr = KK.data[Ns[0]:Ns[0]+Ns[1],Ns[0]:Ns[0]+Ns[1]] #*10.0
            #print(1.0/Kr)
            
            self.sys.init_dephasing_rates()
            self.sys.set_relaxation_rates(1,Kr)
            
            
            #
            # Lineshape functions
            #
            sbi = agg.get_SystemBathInteraction()
            cfm = sbi.CC
            cfm.create_double_integral()
            
            
            #
            # Transformation matrices
            #
            SS = H.diagonalize()
            SS1 = SS[1:Ns[1]+1,1:Ns[1]+1]
            SS2 = SS[Ns[1]+1:,Ns[1]+1:]
            H.undiagonalize()
            
            self.sys.set_gofts(cfm._gofts)    # line shape functions
            self.sys.set_sitep(cfm.cpointer)  # pointer to sites
            self.sys.set_transcoef(1,SS1)  # matrix of transformation coefficients  
            self.sys.set_transcoef(2,SS2)  # matrix of transformation coefficients  

            #
            # Finding population evolution matrix
            #
            prop = PopulationPropagator(self.t1axis, Kr)
      #      Uee, Uc0 = prop.get_PropagationMatrix(self.t2axis,
      #                                            corrections=True)
            self.Uee, cor = prop.get_PropagationMatrix(self.t2axis,
                                                  corrections=3)

            # FIXME: Order of transfer is set by hand here - needs to be moved
            # to some reasonable place
            
            #Ucor = Uee
            self.Uc0 = cor[0]
            
            #for ko in range(No+1):
            #    print("Subtracting ", ko)
            #    Ucor[:,:,tc] -= cor[ko]

            #
            # define lab settings
            #
            if lab is None:
                self.lab = lab_settings(lab_settings.FOUR_WAVE_MIXING)
                X = numpy.array([1.0, 0.0, 0.0], dtype=numpy.float64)
                self.lab.set_laser_polarizations(X,X,X,X)
            else:
                self.lab = lab
            
            #
            # Other parameters
            #
            #dt = self.t1axis.step
            self.rmin = 0.0001
            self.t1s = self.t1axis.data 
            self.t3s = self.t3axis.data
            self.rwa = rwa



            atype = self.t1axis.atype
            self.t1axis.atype = 'complete'
            self.oa1 = self.t1axis.get_FrequencyAxis() 
            self.oa1.data += self.rwa
            self.oa1.start += self.rwa
            self.t1axis.atype = atype
            
            atype = self.t3axis.atype
            self.t3axis.atype = 'complete'
            self.oa3 = self.t3axis.get_FrequencyAxis() 
            self.oa3.data += self.rwa
            self.oa3.start += self.rwa
            self.t3axis.atype = atype
            
        else:
            
            raise Exception("So far, no 2D outside aceto")
            
        self.tc = 0
            
    def calculate_next(self):

        sone = self.calculate_one(self.tc)
        self.tc += 1
        return sone
    
        
    def calculate_one(self, tc):

        tt2 = self.t2axis.data[tc]        
        Nr1 = self.t1axis.length
        Nr3 = self.t3axis.length        
        #
        # Initialize response storage
        #
        resp_r = numpy.zeros((Nr1, Nr3), 
                             dtype=numpy.complex128, order='F')
        resp_n = numpy.zeros((Nr1, Nr3), 
                             dtype=numpy.complex128, order='F')

        # FIXME: on which axis we should be looking for it2 ??? 
        (it2, err) = self.t1axis.locate(tt2) 
        self._vprint("t2 = "+str(tt2)+"fs (it2 = "+str(it2)+")")
        #tc = it2
    
        #
        # calcute response
        #
        self._vprint("calculating response: ")

        t1 = time.time()
        
        self._vprint(" - ground state bleach")
        # GSB
        nr3td.nr3_r3g(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_r) 
        nr3td.nr3_r4g(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_n)
    
        self._vprint(" - stimulated emission")
        # SE
        nr3td.nr3_r1g(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_n)
        nr3td.nr3_r2g(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_r)
        
        self._vprint(" - excited state absorption")
        # ESA
        nr3td.nr3_r1fs(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_r)
        nr3td.nr3_r2fs(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_n)
        
        # Transfer
        
        Utr = self.Uee[:,:,self.tc]-self.Uc0[:,:,self.tc] #-Uc1[:,:,tc]-Uc2[:,:,tc]
        self.sys.set_population_propagation_matrix(Utr) 
        
        self._vprint(" - stimulated emission with transfer")    
        # SE
        nr3td.nr3_r1g_trans(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_n)
        nr3td.nr3_r2g_trans(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_r)
        
#                # This contributes only when No > 0
#                nr3td.nr3_r2g_trN(lab, sys, No, it2, t1s, t3s, rwa, rmin, resp_r)
#                
    
        self._vprint(" - excited state absorption with transfer") 
        # ESA
        nr3td.nr3_r1fs_trans(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_r)
        nr3td.nr3_r2fs_trans(self.lab, self.sys, it2, self.t1s, self.t3s, self.rwa, self.rmin, resp_n)
        
        
        t2 = time.time()
        self._vprint("... calculated in "+str(t2-t1)+" sec")


        #
        # Calculate corresponding 2D spectrum
        #
        
        ftresp = numpy.fft.fft(resp_r,axis=1)
        ftresp = numpy.fft.ifft(ftresp,axis=0)
        reph2D = numpy.fft.fftshift(ftresp)
        
        ftresp = numpy.fft.ifft(resp_n,axis=1)
        ftresp = numpy.fft.ifft(ftresp,axis=0)*ftresp.shape[1]
        nonr2D = numpy.fft.fftshift(ftresp)


        onetwod = TwoDSpectrum()
        onetwod.set_axis_1(self.oa1)
        onetwod.set_axis_3(self.oa3)
        onetwod.set_data(reph2D, dtype="Reph")
        onetwod.set_data(nonr2D, dtype="Nonr")
        
        onetwod.set_t2(self.t2axis.data[tc])
        
        
        return onetwod
                
                
            
    def calculate(self):
        """Returns 2D spectrum
        
        Calculates and returns TwoDSpectrumContainer containing 2D spectrum
        based on the parameters specified in this object.
        
        
        """            
        from .twodcontainer import TwoDSpectrumContainer
                   
        if _have_aceto:

            twods = TwoDSpectrumContainer(self.t2axis)
            
            teetoos = self.t2axis.data
            for tt2 in teetoos:

                onetwod = self.calculate_next()
                twods.set_spectrum(onetwod)   
            
            return twods
        
        else:
            
            # fall back on quantarhei's own implementation
        
            ret = TwoDSpectrumContainer()
            
        
        return ret
    
    
class MockTwoDSpectrumCalculator(TwoDSpectrumCalculator):
    """Calculator of the 2D spectrum from LiouvillePathway objects
    
    
    This class is used to represent LiouvillePatjway objects. Lineshape is
    Gaussian 
    
    """

    def __init__(self, t1axis, t2axis, t3axis):
        #t2axis = TimeAxis()
        super().__init__(t1axis, t2axis, t3axis)
        self.widthx = convert(300, "1/cm", "int")
        self.widthy = convert(300, "1/cm", "int")
        self.dephx = convert(300, "1/cm", "int")
        self.dephy = convert(300, "1/cm", "int")        

        
    def bootstrap(self,rwa=0.0, pathways=None, verbose=False, 
                  shape="Gaussian", all_positive=False):
        
        self.shape = shape
        self.all_positive = all_positive
        
        self.verbose = verbose
        self.rwa = rwa
        self.pathways = pathways

        atype = self.t1axis.atype
        self.t1axis.atype = 'complete'
        self.oa1 = self.t1axis.get_FrequencyAxis() 
        self.oa1.data += self.rwa
        self.oa1.start += self.rwa
        self.t1axis.atype = atype
        
        atype = self.t3axis.atype
        self.t3axis.atype = 'complete'
        self.oa3 = self.t3axis.get_FrequencyAxis() 
        self.oa3.data += self.rwa
        self.oa3.start += self.rwa
        self.t3axis.atype = atype        
        
        self.tc = 0
            

    def set_width(self, val):
        self.widthx = val
        self.widthy = val
        
    def set_deph(self, val):
        self.dephx = val
        self.dephy = val


    def set_pathways(self, pathways):
        self.pathways = pathways
        
        
    def calculate_next(self):

        sone = self.calculate_one(self.tc)
        print(self.tc, sone)
        self.tc += 1
        return sone

        
    def calculate_one(self, tc):
        """Calculate the 2D spectrum for all pathways
        
        """
        
        onetwod = TwoDSpectrum()
        onetwod.set_axis_1(self.oa1)
        onetwod.set_axis_3(self.oa3)
        
        for pwy in self.pathways:
            
            data = self.calculate_pathway(pwy, shape=self.shape)
            
            if pwy.pathway_type == "R":
                onetwod.add_data(data, dtype="Reph")
            elif pwy.pathway_type == "NR":
                onetwod.add_data(data, dtype="Nonr")
            else:
                raise Exception("Unknown pathway type")

        print("Setting: ", self.t2axis.data[tc])
        onetwod.set_t2(self.t2axis.data[tc])    
            
        return onetwod


    def calculate(self):
        """Calculate the 2D spectrum for all pathways
        
        """
        
        onetwod = TwoDSpectrum()
        onetwod.set_axis_1(self.oa1)
        onetwod.set_axis_3(self.oa3)
        
        for pwy in self.pathways:
            
            data = self.calculate_pathway(pwy, shape=self.shape)
            
            if pwy.pathway_type == "R":
                onetwod.add_data(data, dtype="Reph")
            elif pwy.pathway_type == "NR":
                onetwod.add_data(data, dtype="Nonr")
            else:
                raise Exception("Unknown pathway type")

        onetwod.set_t2(0.0)    
            
        return onetwod


    def calculate_pathway(self, pathway, shape="Gaussian"):
        """Calculate the shape of a Liouville pathway
        
        """
 
        noe = 1+pathway.order+pathway.relax_order 
        
        cen1 = pathway.frequency[0]
        cen3 = pathway.frequency[noe-2]
        if self.all_positive:
            pref = numpy.abs(pathway.pref)
        else:
            pref = pathway.pref
            
        N1 = self.oa1.length
        N3 = self.oa3.length
        
        if pathway.widths[1] < 0.0:
            widthx = self.widthx
        else:
            widthx = pathway.widths[1]
            
        if pathway.widths[3] < 0.0:
            widthy = self.widthy
        else:
            widthy = pathway.widths[3]
            
        if pathway.dephs[1] < 0.0:
            dephx = self.dephx
        else:
            dephx = pathway.dephs[1]
            
        if pathway.widths[3] < 0.0:
            dephy = self.dephy
        else:
            dephy = pathway.dephs[3]
        
        #print(shape, widthx, widthy)
        
        if pathway.pathway_type == "R":

            reph2D = numpy.zeros((N1, N3), dtype=qr.COMPLEX)
            
            if shape == "Gaussian":
                oo3 = self.oa3.data[:]
                for i1 in range(N1):
                    o1 = -self.oa1.data[i1]                    
                        
                    reph2D[:, i1] = \
                    pref*numpy.exp(-((o1-cen1)/widthx)**2)\
                        *numpy.exp(-((oo3-cen3)/widthy)**2)
            
            elif shape == "Lorentzian":
                oo3 = self.oa3.data[:]
                for i1 in range(N1):
                    o1 = -self.oa1.data[i1]                    
                        
                    reph2D[:, i1] = \
                    pref*(dephx/((o1-cen1)**2 + dephx**2))\
                        *(dephy/((oo3-cen3)**2 + dephy**2))
                        
            else:
                raise Exception("Unknown line shape: "+shape)   
            
            return reph2D
            
        elif pathway.pathway_type == "NR":
           
            nonr2D = numpy.zeros((N1, N3), dtype=qr.COMPLEX)
            
            if shape == "Gaussian":
                oo3 = self.oa3.data[:]
                for i1 in range(N1):
                    o1 = self.oa1.data[i1]                    
                    
                    nonr2D[:, i1] = \
                    pref*numpy.exp(-((o1-cen1)/widthx)**2)\
                        *numpy.exp(-((oo3-cen3)/widthy)**2)
                        
            elif shape == "Lorentzian":
                oo3 = self.oa3.data[:]
                for i1 in range(N1):
                    o1 = self.oa1.data[i1]                    
                        
                    nonr2D[:, i1] = \
                    pref*(dephx/((o1-cen1)**2 + dephx**2))\
                        *(dephy/((oo3-cen3)**2 + dephy**2))

            else:
                raise Exception("Unknown line shape: "+shape)
            
            return nonr2D
        
            
        
        