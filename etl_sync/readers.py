"""
Reader classes for ETL.
"""
from osgeo import ogr


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
    ShapefileReader compatible to csv.DictReader (only within the context
    below). Would be great to make this fully compatible. See pyshp as
    an example already doing it (not using ogr).
    """

    def __init__(self, source, encoding='utf-8'):
        if hasattr(source, 'name'):
            s = source.name
            source.close()
            source = s
        self.encoding = encoding
        self.shapefile = ogr.Open(source)
        self.layer = self.shapefile.GetLayer(0)
        self.srs = self.layer.GetSpatialRef()

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
            ret['geometry'] = feature.geometry().ExportToWkt()
            return ret
