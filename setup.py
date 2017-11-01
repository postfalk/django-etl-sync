from __future__ import unicode_literals
import os
from setuptools import setup


os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setup(
    name='django-etl-sync',
    version='0.3.2',
    packages=['etl_sync'],
    include_package_data=True,
    license='BSD License',
    description='Django ETL, derives rules from models, creates relations.',
    url='https://github.com/postfalk/django-etl-sync.git',
    download_url='https://github.com/postfalk/django-etl-sync/tarball/0.3.2',
    author='Falk Schuetzenmeister',
    author_email='schuetzenmeister@berkeley.edu',
    install_requires=['future', 'six', 'backports.csv'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content']
)
