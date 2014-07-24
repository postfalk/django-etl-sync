import os
import sys
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
            }
        },
        MEDIA_ROOT=os.path.dirname(
            os.path.realpath(__file__))+'/tests',
        ROOT_URLCONF='etl_sync.tests.urls',
        INSTALLED_APPS=(
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.admin',
            'tests'
        ),
    )

from django.test.simple import DjangoTestSuiteRunner
testrunner = DjangoTestSuiteRunner(verbosity=1)
failures = testrunner.run_tests(['tests'])
if failures:
    sys.exit(failures)
