import os
from setuptools import setup

README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-etl-sync',
    version='0.2',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Framework :: Django',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Software Development :: Libraries',
    ],
    packages=['etl_sync'],
    include_package_data=True,
    license='BSD License',
    description='Django ETL, derives rules from models, creates relations.',
    long_description='README.md',
    url='https://github.com/postfalk/django-etl-sync.git',
    download_url='https://github.com/postfalk/django-etl-sync/tarball/0.2',
    author='Falk Schuetzenmeister',
    author_email='schuetzenmeister@berkeley.edu',
    install_requires=['unicodecsv', 'future', 'six'],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
