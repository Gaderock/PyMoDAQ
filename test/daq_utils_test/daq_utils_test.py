import numpy as np
import pytest
from pymodaq.daq_utils import daq_utils
import datetime
class TestJsonConverter:
    def test_object2json(self):
        conv = daq_utils.JsonConverter()
        assert conv.istrusted('datetime')
        d = datetime.datetime(year=2020, month=5, day=24, hour=10, minute=52, second=55)
        date = d.date()
        time = d.time()
        dstring = '{"module": "datetime", "type": "datetime", "data": "datetime.datetime(2020, 5, 24, 10, 52, 55)"}'
        datestring = '{"module": "datetime", "type": "date", "data": "datetime.date(2020, 5, 24)"}'
        timestring = '{"module": "datetime", "type": "time", "data": "datetime.time(10, 52, 55)"}'
        assert conv.object2json(d) == dstring
        assert conv.json2object(dstring) == d
        assert conv.object2json(date) == datestring
        assert conv.json2object(datestring) == date
        assert conv.object2json(time) == timestring
        assert conv.json2object(timestring) == time
        assert conv.json2object(conv.object2json([10, 5, 'yui'])) == [10, 5, 'yui']
        assert conv.json2object(conv.object2json((10, 5, 'yui'))) == (10, 5, 'yui')

class TestUnits:
    def test_Enm2cmrel(self):
        assert daq_utils.Enm2cmrel(520, 515) == pytest.approx(186.70649738)

    def test_Ecmrel2Enm(self):
        assert daq_utils.Ecmrel2Enm(500, 515) == pytest.approx(528.6117526)

    def test_eV2nm(self):
        assert daq_utils.eV2nm(1.55) == pytest.approx(799.89811299)

    def test_nm2eV(self):
        assert daq_utils.nm2eV(800) == pytest.approx(1.54980259)

    def test_eV2cm(self):
        assert daq_utils.eV2cm(0.07) == pytest.approx(564.5880342655)

    def test_l2w(self):
        assert daq_utils.l2w(800) == pytest.approx(2.35619449)

class TestString:
    def test_capitalize(self):
        string = 'abcdef'
        assert daq_utils.capitalize(string) == 'Abcdef'

    def test_uncapitalize(self):
        string = 'Abcdef'
        assert daq_utils.uncapitalize(string) == 'abcdef'

def test_ListPicker():
    pass

def test_get_data_dimension():
    shapes = [(), (1,), (10,), (5, 5)]
    scan_types = ['scan1D', 'scan2D']
    remove = [False, True]
    for shape in shapes:
        for scan in scan_types:
            for rem in remove:
                arr = np.ones((shape))
                size = arr.size
                dim =  len(arr.shape)
                if dim == 1 and size == 1:
                    dim = 0
                if rem:
                    if scan.lower() == 'scan1d':
                        dim -= 1
                    if scan.lower() == 'scan2d':
                        dim -= 2
                assert daq_utils.get_data_dimension(arr, scan, rem) == (shape, '{:d}D'.format(dim), size)

class TestScroll:
    def test_scroll_log(self):
        min_val = 50
        max_val = 51
        for scroll_val in range(101):
            assert daq_utils.scroll_linear(scroll_val, min_val, max_val) == pytest.approx(10**(scroll_val * (np.log10(max_val)-np.log10(min_val))/100+ np.log10(min_val)))

    def test_scroll_linear(self):
        min_val = 50
        max_val = 51
        for scroll_val in range(101):
            assert daq_utils.scroll_linear(scroll_val, min_val, max_val) == pytest.approx(scroll_val * (max_val-min_val)/100+ min_val)

def test_extract_TTTR_histo_every_pixels():
    pass

def test_ScanParameters():
    Nsteps = 10
    axis_1_indexes = []
    axis_2_indexes = []
    axis_1_unique = []
    axis_2_unique = [],
    positions = []
    scan_param = daq_utils.ScanParameters(Nsteps, axis_1_indexes, axis_2_indexes, axis_1_unique, axis_2_unique,
                        positions)
    assert scan_param.Nsteps is Nsteps
    assert axis_1_indexes is axis_1_indexes
    assert axis_2_indexes is axis_2_indexes
    assert axis_1_unique is axis_1_unique
    assert axis_2_unique is axis_2_unique

def test_ThreadCommand():
    command = 'abc'
    attributes = [1,3]
    threadcomm = daq_utils.ThreadCommand(command,attributes)
    assert threadcomm.command is command
    assert threadcomm.attributes is attributes

def test_elt_as_first_element():
    elts = ['test', 'tyuio', 'Mock', 'test2']
    elts_sorted = daq_utils.elt_as_first_element(elts[:])
    assert elts_sorted[0] == 'Mock'
    for ind in range(1,len(elts)):
        assert elts_sorted[ind] in elts
    elts_sorted = daq_utils.elt_as_first_element(elts[:], elts[1])
    assert elts_sorted[0] == elts[1]

