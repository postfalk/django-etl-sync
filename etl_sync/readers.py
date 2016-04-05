# Python 3 compatibility
from __future__ import print_function
from future.utils import iteritems

import warnings
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
    OGRReader for supported OGR formats. Partially (duck-typed)
    compatible with csv.DictReader.

    Args:
        source (bytes): Complete path to the source file.
        encoding (Optional[bytes]): Encoding string. Defaults to 'utf-8'.
        delimiter (Optional[bytes]): Unused. Here for compatibility.
        quoting (Optional[bytes]): Unused. Here for compatibility.
        target_epsg (Optional[int]): Spatial reference. Defaults to 4326.
        feature_class_name (Optional[bytes]): Name of the feature class within ds.
            Defaults to the first returned by GDAL.
    """

    def __init__(self, source, encoding='utf-8',
                 delimiter='', quoting='', target_epsg=4326,
                 feature_class_name=''):
        if hasattr(source, 'name'):
            s = source.name
            source.close()
            source = s
        self.encoding = encoding
        self.ds = ogr.Open(source)
        if not feature_class_name:
            self.layer = self.ds.GetLayer(0)
        else:
            self.layer = self.ds.GetLayerByName(
                feature_class_name)
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
    """
    For compatibility with older versions.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(DeprecationWarning)
        super(ShapefileReader, self).__init__(*args, **kwargs)
