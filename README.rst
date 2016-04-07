Django ETL Sync
===============

.. image:: https://travis-ci.org/postfalk/django-etl-sync.svg?branch=master
    :target: https://travis-ci.org/postfalk/django-etl-sync
.. image:: https://coveralls.io/repos/postfalk/django-etl-sync/badge.png?branch=master
    :target: https://coveralls.io/r/postfalk/django-etl-sync?branch=master
.. image:: https://pypip.in/v/postfalk/django-etl-sync/badge.png
    :target: https://crate.io/packages/postfalk/django-etl-sync/
    :alt: Latest PyPI version
.. image:: https://pypip.in/d/postfalk/django-etl-sync/badge.png
    :target: https://crate.io/packages/django-etl-sync/
    :alt: Number of PyPI downloads

ETL based on Django model introspection.

Django-etl-sync derives ETL rules from Django model introspection and is able to trace and create relationships such as foreign keys and many-to-many relationship.

The package currently lacks a method to move records no longer present in upstream data.


Overview
--------

- Re-usable Django app that provides classes for light weight ETL in your project. (Will be more independent from the Django framework in the future)
- Geared toward sync'ing with upstream data sources (e.g. for an API) or legacy data (it was originally build for ecoengine.berkeley.edu loading million records from museum collection data with regular small changes).
- Prioritizes data consistency over speed.
- Subclassing allows for replacing of methods with speedier, simplified or more sophisticated versions.
- Supports data persistence, consistency, normalization, and recreation of relationships from flatten files or dumps.
- Derives ETL rules from Django model introspection (the use of other frameworks or database declarations is planned). This rules can be easily modified and overriden (as long as they do not cause integrity errors).
- Can be easily used within a parallelization framework such as Celery, thorough checks of the state of the destination avoid race conditions and inconsistencies (at the cost of speed.)
- Supports Django Forms as transformation rules. This way web forms within the app can be re-used as transformation rules.

Requirements
------------

- Python 2.7 upwards, Python 3
- Django 1.7 (tested) upwards
- GDAL if OGR readers for geodata are used

Installation
------------

The package is in active development toward a release. For evaluation, contribution, and testing

.. code-block:: sh

    pip install -e git+ssh://git@github.com/postfalk/django-etl-sync#egg=django-etl-sync

or for usage

.. code-block:: sh

    pip install django-etl-sync

Add ``etl_sync`` to ``INSTALLED_APPS`` in settings.py of your Django project.

Minimal Examples
----------------

The module provides two principal ways of usage on either file or record level.

1. Use the ``Loader`` class to specify all ETL operations. If you need to make changes to the data between reading from the file and writing them to the database create a custom ``Transformer`` class (see below).

The loader class was called Mapper in earlier versions. There is still a ``Mapper`` class which is a wrapper of the ``Loader`` class that will throw an deprecation warning upon initialization (removal planned for version 1.0). Applications that were build using older versions will work for now.

2. Use the ``Generator`` class to generate a Django model instance from a dictionary and return the instance. The input dictionary needs to satisfy all constraints of the model as defined by the ``ModelField`` attributes. If this is not the case an error will be thrown. The ``Loader`` class will catch this error and create a log entry. Apply transformations beforehand.

The difference to simply creating an instance by calling ``Model(**dict)`` is a very thorough check for consistency and the creation of relationships. However, if the simple method is convenient, a Django Model could be used in place of the ``Generator``.

Minimal example: file load
--------------------------

.. code-block:: python

    # data.txt
    record  name
    1 one
    2 two
    3 three


    # main.py
    from django.db import models
    from etl_sync.loaders import Loader

    class TestModel(models.Model):
        """
        Example Model.
        """
        record = models.CharField(max_length=10)
        name = models.CharField(max_length=10, null=True, blank=True)


    class YourLoader(Loader):
        """
        Add your specific settings here.
        """
        filename = 'data.txt'
        model_class = TestModel


    if __name__ == '__main__':
        loader = YourLoader()
        res = loader.load()


Minimal example: dictionary load
--------------------------------

.. code-block:: python

    # main.py
    from etl_sync.generators import BaseInstanceGenerator
    from <yourproject>.models import TestModel

    dic = {'record': 3, 'name': 'three'}

    if __name__ == '__main__':
        # add additional transformations here
        generator = BaseInstanceGenerator(TestModel, dic)
        instance = generator.get_instance()
        print(instance, generator.res)


Persistence
-----------

**Unique fields**

Before loading a record it might be necessary to check whether it already exists, whether it needs to be added or updated (persistence). By default the module inspects the target model and uses model fields with the attribute ``unique=True`` as criterion for persistence. The module will check first whether any record with the given combination of values in unique fields already exists and update that record.

.. note:: Do not use the models internal pk or id field as identifier for your data! Add an extra field containing the identifier from the upstream source, such as ``record`` or ``remote_id``.

**Extra arguments**

Another method to add (or overwrite) persistence criterions is to add a list of fields via key word argument.

.. code-block:: python

    generator = InstanceGenerator(
        TestModel, dic, persistence = ['record', 'source'])

**Subclassing**

You can subclass InstanceGenerator to create your own generator class with a specific persistence criterion.

.. code-block:: python

    from etl_sync.generators import InstanceGenerator

    class MyGenerator(InstanceGenerator):
        """
        My generator class with custom persistence criterion.
        """
        persistence = ['record', 'source']


``etl_persistence`` **key in data dictionary**

The last method is to put an extra key value pair in your data dictionary, e.g. during the dictionary transformation.

.. code-block:: python

    dic = {'record': 6365, 
           'name': 'john', 
           'occupation': 'developer', 
           'etl_persistence': ['record']}


This approach is particular helpful for nested records that can be used to create relationships. It seems likely that the related model has different persistence criteria than the model currently loaded. In a recursive call, the ``InstanceGenerator`` might not be
directly accessible (see below). E.g.

.. code-block:: python

    dic = {'record': 6565, 
           'name': 
           'john', 
           'occupation': {
                'name': 'developer', 
                'paygroup': 'III', 
                'etl_persistence': ['name', 'paygroup']}}

If the instance generator is called like this and the ``create_foreignkey`` attribute is ``True``, the foreign key entry for developer with paygroup III will be generated if not already existent.

In addition the key value pair ``etl_create: True`` can be set on nested records to create (or prevent the creation if set ``False``) of nested records.

If record creation is disabled and the persistence criterion cannot be met, the record will be rejected and the rejection logged in the logfile when using ``Loader``.

**Defining persistence by a Django ModelField attributes requiring a concise data model is the preferred method.**

Once the attribute **persistence** is set on the ``Generator`` class the model field attributes will be ignored as a source for persistence rules. Nevertheless, conflicts with your Django models will throw ``IntegrityError`` or other database errors. 

Error handling
--------------

If the ``Generator`` class is called within the ``Mapper`` class, errors will be caught and written to the defined logfile or to stdout. The loading process will continue. In contrast, if you use the ``Generator`` class in a different context you need to catch errors in your code 

Readers
-------

By default django-etl-sync uses the Python ``csv.DictReader``, other reader classes can be used or created if they are similar (duck-typed) to ``csv.DictReader``.

The package currently contains a reader for OGR readable files.

.. code-block:: python

    from etl_sync.generators import InstanceGenerator
    from etl_sync.readers import OGRReader

    class MyMapper(Mapper):
        reader_class=OGRReader
        
The ``OGRReader`` *covers the functionality of the older* ``ShapefileReader`` class there is still a stub ``ShapefileReader`` for compatibility. It will be removed in version 1.0.

Transformations
---------------

Transformations remap the dictionary from the CSV reader or another reader class to the Django model. We attempt to map the
dictionary key to the model field with the matching name. The ``Transformer`` classes allows for remapping and validation of incoming records.

Instantiate ``InstanceGenerator`` with a customized ``Transformer`` class:

.. code-block:: python

    from etl_sync.loaders import Loader
    from etl_sync.transformes import Transformer

    class MyTransformer(Transformer):
        mappings = {'id': 'record', 'name': 'last_name'}
        defaults = {'last_name': 'Doe'}
        forms = []
        blacklist = {'last_name': ['NA', r'unknown']}

    class MyLoader(Loader):
        model_class = {destination model}
        transformer_class = MyTransformer

    loader = MyLoader(filename=myfile.txt)
    loader.load()


* The `mapping` property contains a dictionary in the form ``{‘original_fieldname’: ‘new_fieldname’}`` which will remap the dictionary.
* The `defaults` property holds a dictionary that gets applied if the value for the dictionary key in question is empty.
* The `forms` property holds a list of Django forms that get applied to the dictionary. Be careful, unused keys will not be removed. The new ``cleaned_data`` keys will be *added* to the dictionary.
* And finally the `blacklist` property holds a list of values for particular keys that will trigger a validation error. The record will be discarded.

.. note:: These methods will be applied in exactly that order. If the dictionary changes in one of these steps, the next step needs to take these changes into consideration.

In addition to these built-in transformations, there are two additional methods that can be modified for more thorough changes:

.. code-block:: python

    class MyTransformer(Transformer):

        def transform(self, dic):
            """Make whatever changes needed here."""
            return dic

        def validate(self, dic):
            """Raise ValidationErrors"""
            if last_name == 'Bunny':
                raise ValidationError('I do not want to have this record')

Both methods will be applied after the aforementioned built-in methods encouraging a declarative style.


**Django form support**

A generic Django form class can also be used as ``Loader.transformer_class``.

**Create transformer for related models**

Alternative strategies for loading normalized or related data
-------------------------------------------------------------

Table dumps of related tables
-----------------------------

Creating related tables from same data source
---------------------------------------------

File load
---------

Loging
------

Django-etl-sync will create a log file in the same location as the source file.
It will contain the list of rejected records.

.. code-block: sh
    source_file.txt
    source_file.txt.2014-07-23.log

Roadmap
-------

- Create readers for more source types, especially for comma limited data, and headerless CSV.
- Add a way for data removal, if deleted from source.
- Improve Documentation, create documention on ReadTheDocs.
