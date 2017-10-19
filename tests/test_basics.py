from __future__ import print_function
from unittest import TestCase
import sys
import gdal
import django


class ReportingTestCase(TestCase):
    """
    Just a few prints in order to monitor whether variables in .travis
    are set correctly.
    """

    def test_travis(self):
        print('Django', django.VERSION)
        print('Python', sys.version_info)
        print('GDAL', gdal.VersionInfo())
