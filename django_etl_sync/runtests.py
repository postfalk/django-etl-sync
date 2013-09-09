import os
import sys

from django.conf import settings

if not settings.configured:

    settings.configure(
        DATABASE_ENGINE='sqlite3',
        ROOT_URLCONF='django_etl_sync.tests.urls',
        INSTALLED_APPS=(
            'django_etl_sync',
            'django_etl_sync.tests',
        )
    )

from django.test.simple import DjangoTestSuiteRunner
test_runner = DjangoTestSuiteRunner(verbosity=1)
failures = test_runner.run_tests(['django_etl_sync.tests', ])
if failures:
    sys.exit(failures)
