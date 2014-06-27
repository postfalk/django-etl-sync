"""
Reader classes for ETL.
"""
from osgeo import ogr
from osgeo import osr


def unicode_dic(dic, encoding):
    """
    Decodes entire dictionary with given encoding.
    """
    for key, value in dic.iteritems():
        if isinstance(value, str):
            dic[key] = unicode(value, encoding)
    return dic


class ShapefileReader(object):
    """
    ShapefileReader is compatible to csv.DictReader (only within the context
    of this project). Would be great to make this fully compatible.
    See pyshp as an example already doing it (not using ogr).
    """

    def __init__(self, source, encoding='utf-8'):
        if hasattr(source, 'name'):
            s = source.name
            source.close()
            source = s
        self.encoding = encoding
        self.shapefile = ogr.Open(source)
        self.layer = self.shapefile.GetLayer(0)
        source = self.layer.GetSpatialRef()
        target = osr.SpatialReference()
        target.ImportFromEPSG(4326)
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
