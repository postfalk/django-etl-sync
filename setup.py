import os
from setuptools import setup

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-etl-sync',
    version='0.1',
    packages=['etl_sync'],
    include_package_data=True,
    license='BSD License', # example license
    description="A ETL tool to sync API's.",
    long_description=README,
    url='https://github.com/postfalk/django-etl-sync.git',
    author='Falk Schuetzenmeister',
    author_email='schuetzenmeister@berkeley.edu',
    install_requires=['osgeo'],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License', # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # replace these appropriately if you are using Python 3
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)

