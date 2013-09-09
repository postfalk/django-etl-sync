import os
import sys
from django.conf import settings

settings.configure(DEBUG=True,
               DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                    }
                },
               INSTALLED_APPS=('django.contrib.auth',
                              'django.contrib.contenttypes',
                              'django.contrib.sessions',
                              'django.contrib.admin',
                              'bee.django_etl_sync',
                              'bee.django_etl_sync.tests'))

from django.test.simple import DjangoTestSuiteRunner
test_runner = DjangoTestSuiteRunner(verbosity=1)
failures = test_runner.run_tests(['bee.django_etl_sync.tests', ])
if failures:
    sys.exit(failures)
