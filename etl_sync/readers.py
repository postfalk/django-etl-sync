from osgeo import ogr
import unicodecsv as csv

class ShapefileReader(object):
    """
    ShapefileReader compatible to csv.DictReader (only within the context below).
    Would be great to make this fully compatible. See pyshp as an example already
    doing it (not using ogr).
    """

    def __init__(self, source):
        if hasattr(source, 'name'):
            s = source.name
            source.close()
            source = s
        self.shapefile = ogr.Open(source)
        self.layer = self.shapefile.GetLayer(0)

    def length(self):
        return self.layer.GetFeatureCount()

    def next(self):
        feature = self.layer.GetNextFeature()
        try:
            ret = feature.items()
        except AttributeError:
            raise StopIteration
        else:
            ret['geometry'] = feature.geometry().ExportToWkt()
            return ret

