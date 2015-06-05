import os
import sys
from django.conf import settings
import django

DEFAULT_SETTINGS = {
    'DATABASES': {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.spatialite',
            'NAME': ':memory:'
            }
        },
    'MEDIA_ROOT': os.path.dirname(os.path.realpath(__file__))+'/tests',
    'ROOT_URLCONF': 'tests.urls',
    'INSTALLED_APPS': (
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.admin',
        'etl_sync',
        'tests'
    ),
    'MIDDLEWARE_CLASSES': (
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
    ),
    'PROJECT_ROOT': os.path.join(
        *os.path.realpath(__file__).split('/')[0:-2])
}


def teardown():
    pass


def runtests():
    if not settings.configured:
        settings.configure(**DEFAULT_SETTINGS)
    if hasattr(django, 'setup'):
        django.setup()
    sys.path.insert(0, settings.PROJECT_ROOT)
    try:
        from django.test.runner import DiscoverRunner
        runner_class = DiscoverRunner
    except ImportError:
        from django.test.simple import DjangoTestSuiteRunner
        runner_class = DjangoTestSuiteRunner
    testrunner = runner_class(
        verbosity=1, interactive=True, failfast=False)
    try:
        status = testrunner.run_tests(['tests'])
    except:
        status = 1
    finally:
        teardown()
    sys.exit(status)

if __name__ == '__main__':
    runtests()
