# Python 3 compatibility
from __future__ import print_function
from future.utils import iteritems

from osgeo import osr, ogr

def unicode_dic(dic, encoding):
    """
    Decodes bytes dictionary to unicode with given encoding.
    """
    new_dic = {}
    for key, value in iteritems(dic):
        if isinstance(value, bytes):
            value = value.decode(encoding)
        if isinstance(key, bytes):
            key = key.decode(encoding)
        new_dic[key] = value
    return new_dic


class OGRReader(object):
    """
    OGRReader for all OGR formats. Partially (duck-typed)
    compatible with csv.DictReader.
    """

    def __init__(self, source, encoding='utf-8',
                 delimiter='', quoting='', target_epsg=4326):
        if hasattr(source, 'name'):
            s = source.name
            source.close()
            source = s
        self.encoding = encoding
        self.shapefile = ogr.Open(source)
        self.layer = self.shapefile.GetLayer(0)
        source = self.layer.GetSpatialRef()
        target = osr.SpatialReference()
        target.ImportFromEPSG(target_epsg)
        self.transform = osr.CoordinateTransformation(source, target)

    def length(self):
        return self.layer.GetFeatureCount()

    def next(self):
        feature = self.layer.GetNextFeature()
        try:
            ret = feature.items()
        except AttributeError:
            raise StopIteration
        else:
            ret = unicode_dic(ret, self.encoding)
            ogr_geom = feature.geometry()
            ogr_geom.Transform(self.transform)
            ret['geometry'] = ogr_geom.ExportToWkt()
            return ret


class ShapefileReader(OGRReader):
    """For compatibility"""
