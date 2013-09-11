import os
import sys

from django.conf import settings

if not settings.configured:

    settings.configure(
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
            }
        },
        MEDIA_ROOT = os.path.dirname(os.path.realpath(__file__))+'/tests',
        ROOT_URLCONF='etl_sync.tests.urls',
        INSTALLED_APPS=(
            'etl_sync',
            'etl_sync.tests',
        )
    )

from django.test.simple import DjangoTestSuiteRunner
test_runner = DjangoTestSuiteRunner(verbosity=1)
failures = test_runner.run_tests(['tests', ])
if failures:
    sys.exit(failures)
