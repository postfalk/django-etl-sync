# Python 3.x compatibility
from __future__ import absolute_import
from six import text_type
from future.utils import iteritems

import os
from unittest import TestCase
from etl_sync.readers import unicode_dic, OGRReader

class TestReaders(TestCase):
    """
    Test readers, encoding problems in particular.
    """

    def setUp(self):
        path = os.path.dirname(os.path.realpath(__file__))
        self.testfilename = os.path.join(path, 'shapefile.shp')

    def test_dic_decoder(self):
        testdic = {
            'word': b'testword', 'number': 68898, 'utf8': b'testing\xc2\xa0'}
        dic = unicode_dic(testdic, 'utf-8')
        self.assertEqual(dic['utf8'], u'testing\xa0')
        for k, v in iteritems(dic):
            self.assertIsInstance(k, text_type)

    def test_ogr_reader(self):
        reader = OGRReader(self.testfilename)
        dic = reader.next()
        self.assertEqual(dic['text'], u'three')
        dic = reader.next()
        self.assertEqual(dic['text'], u'two')
