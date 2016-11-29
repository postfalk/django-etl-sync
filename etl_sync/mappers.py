"""
Ensure compatibility with older versions.
"""
import warnings
from etl_sync.loaders import Loader


class Mapper(Loader):

    def __init__(self, *args, **kwargs):
        warnings.warn(
            'Mapper class will be deprecated '
            'in release 1.0, use Loader instead.',
            DeprecationWarning)
        super (Mapper, self).__init__(*args, **kwargs)
