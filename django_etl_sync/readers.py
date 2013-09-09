from osgeo import ogr
import unicodecsv as csv


class ShapefileReader(object):
    """
    ShapefileReader compatible to csv.DictReader (only within the context below).
    Would be great to make this fully compatible. See pyshp as an example already
    doing it (not using ogr).
    """
    # This one is based on OGR since this dependency will be required throughout
    # BEE. There is an easier way using http://code.google.com/p/pyshp/ which is
    # quite similar to DictReader.
    # TODO: Create one based on django.gdal module?

    def __init__(self, source):
        # the file reference needs to kept alive here to work in other methods
        # see http://trac.osgeo.org/gdal/ticket/4914
        # extract filename if argument is filehandle
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
