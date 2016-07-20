# -*- coding: utf-8 -*-

import unittest

"""
*******************************************************************************


    Tests of the quantarhei.energy_units class


*******************************************************************************
"""  
from quantarhei.core import UnitsManaged

from quantarhei import energy_units
from quantarhei.core.units import cm2int

# let us reuse a class from previous test
from .test_UnitsManaged import UnitsManagedObject        

class TestEnergyUnits(unittest.TestCase):
    
    def setUp(self):
        # reusining class from previous test
        self.u = UnitsManagedObject()
        
    def test_using_different_units(self):
        """Testing that 'energy_units' context manager works
        
        """
        # set value in 1/cm
        with energy_units("1/cm"):
            val = 100.0
            self.u.set_value(val)
            
        # compare it in internal units
        self.assertEqual(self.u.value,val*cm2int)
        
        
