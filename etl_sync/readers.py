"""
Reader classes for ETL.
"""
from osgeo import osr, ogr


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
    ShapefileReader reads ESRI shape files and is partially
    compatible with csv.DictReader (currently only within the context
    of this project.
    """

    def __init__(self, source, encoding='utf-8',
                 delimiter='', quoting=''):
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
