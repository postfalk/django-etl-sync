# Django ETL Sync

ETL based on Django model introspection

[![Build Status][travis-image]][travis-link]
[![Coverage Status][coveralls-image]][coveralls-link]

---

## Overview

- Re-usable Django app that provides classes for light weight ETL in your 
project. (Will be more independent from the Django framework in the future)

- Geared toward sync'ing with upstream data sources (e.g. for an API) or 
legacy data (it was originally build for ecoengine.berkeley.edu loading
million records from museum collection data with regular small changes).

- Prioritizes data consistency over speed.

- Subclassing allows for replacing of methods with speedier, simplified 
or more sophisticated versions.

- Supports data persistence, consistency, normalization, and recreation 
of relationships from flatten files or dumps.

- Derives ETL rules from Django model introspection (the use of other 
frameworks or database declarations is planned). This rules can be easily 
modified and overriden (as long as they do not cause integrity errors).

- Can be easily used within a parallelization framework such as Celery, 
thorough checks of the state of the destination avoid race conditions and 
inconsistencies (at the cost of speed.)

- Supports Django Forms as transformation rules. This way web forms within 
the app can be re-used as transformation rules.


## Requirements

- Python 2.7 upwards, Python 3
- Django 1.6.6 upwards
- GDAL if OGR readers for geodata are used


## Tutorial

### Installation

The package is in active development toward a release. For evaluation, contribution, and testing.

```bash
pip install -e git+ssh://git@github.com/postfalk/django-etl-sync#egg=django-etl-sync
````

Add `etl_sync` to `INSTALLED_APPS` in settings.py.

### Minimal Examples

The module provides two principal ways of usage on either file or record level.

1. Use the `Loader` class to specify all ETL operations. If you need
to make changes to the data between reading from the file and writing them to the
database create a costum `Transformer` class (see below).

*The loader class was called Mapper in earlier versions. There is still a* `Mapper` 
*class which is a wrapper of the* `Loader` *class that will throw an deprecation 
warning upon initialization (removal planned for version 1.0). Applications that 
were build with the older version will still work for now.*

2. Use the `Generator` to generate a Django model from a dictionary and 
return an instance. The input dictionary needs to satisfy the the requirements 
of the model. Apply transformations beforehand.

The difference to simply create an instance by Model(**dict) is the thorough check
for consistency and the creation of relationships. However, if the simple method 
is convenient, a Django Model could be used in place of the Generator.

#### Minimal example: file load:

```python
# data.txt
record  name
1 one
2 two
3 three


# models.py
from django.db import models

class TestModel(models.Model):
    """
    Example Model.
    """
    record = models.CharField(max_length=10)
    name = models.CharField(max_length=10, null=True, blank=True)


# <yourscript>.py
from etl_sync.loader import Loader
from <yourproject>.models import TestModel

class YourLoader(Loader):
    """
    Add your specific settings here.
    """
    filename = 'data.txt'
    model_class = TestModel

    if __name__ == '__main__':
        loader = YourLoader()
        res = loader.load()
```


#### Minimal example: dictionary load


```python

# <yourscript>.py
from etl_sync.generators import BaseInstanceGenerator
from <yourproject>.models import TestModel

dic = {'record': 3, 'name': 'three'}

if __name__ == '__main__':
    # add additional transformations here
    generator = BaseInstanceGenerator(TestModel, dic)
    instance = generator.get_instance()
    print(instance, generator.res)
```


### Persistence

**Unique fields**

Before loading a record it might be necessary to check whether 
it already exists, whether it needs to be added or updated 
(persistence). By default the module inspects the target model 
and uses model fields with the attribute unique=True as criterion 
for persistence. The module will check first whether any record with 
the given combination of values in unique fields already exists and 
update that record.

<font color='red'>WARNING: Do not use the models internal pk or 
id field as identifier for your data! Add an extra record or 
remote_id field.</font>*

**Extra arguments**

Another method to add (or overwrite) persistence criterions is to add a 
a list of fields via key word argument.

```python
    generator = InstanceGenerator(TestModel, dic, persistence = ['record', 'source'])
```


**Subclassing**

You can subclass InstanceGenerator to create your own generator class.

```python
from etl_sync.generators import InstanceGenerator

class MyGenerator(InstanceGenerator):
    """
    My generator class with costum persistence criterion.
    """
    persistence = ['record', 'source']
```

**etl_persistence key in data dictionary**

The last method is to put an extra key value pair in your data dictionary.

```python
dic = {'record': 6365, 'name': 'john', 'occupation': 'developer', 'etl_persistence': ['record']}
```

This technique is useful for nested records if the recursive call of
InstanceGenerator cannot be
directly accessed (see below). However ...

**Defining persistence by a field attributes and a concise data model is the 
preferred method.**

Once the variable **persistence** is overwritten the model field attributes 
will be ignored. Nevertheless, conflicts with your data definition will 
through database errors. 

### Error handling ###

If the Generator class is called within the Mapper class, errors will
be caught and written to the defined logfile or to stdout. But the 
loading process will continue. 

## Readers ##

By default django-etl-sync uses the csv.DictReader, other reader 
classes can be used or created if they are similar to csv.DictReader.

The package currently contains a reader for OGR readable files.

```python
from etl_sync.generators import InstanceGenerator
from etl_sync.readers import OGRReader

class MyMapper(Mapper):
    reader_class=OGRReader
```

*The* ```OGRReader``` *covers the functionality of the older* ```ShapefileReader``` *.
There is still a stub class called ShapefileReader for compatibility.
It will be removed in version 1.0.*

## Transformations

Transformations remap the dictionary from the CSV reader or
another reader class to the Django model. We attempt to map the
dictionary key to the model field with the matching name.
The transformer classes allow for remapping and validation of incoming
records.

Instantiate InstanceGenerator with a costumized Transformer class:

```python
from etl_sync.loaders import Loader
from etl_sync.transformes import Transformer

class MyTransformer(Transformer):
    mappings = {'id': 'record', 'name': 'last_name'}
    defaults = {'last_name': 'Doe'}
    forms = []
    blacklist = {'last_name': ['NA', r'unknown']}

class MyMapper(InstanceGenerator):
    model_class = {destination model}
    transformer_class = MyTransformer
    filename = myfile.txt

loader = MyLoader()
loader.load()
```

* The `mapping` property contains a dictionary in the form `{‘original_fieldname’: ‘new_fieldname’}` which will remap the dictionary.
* The `defaults` property holds a dictionary that gets applied if the value for the dictionary key in question is empty.
* The `forms` property holds a list of Django forms that get applied to the dictionary. WARNING: old values will not be removed. The cleaned_data keys will be added to the dictionary.
* And finally the `blacklist` property holds a list of values for a particular key that will trigger a validation error. The record will be discarded.

WARNING: These methods will be applied in exactly that order. If the dictionary changes in one of these steps, the next step needs to take these changes into consideration.

In addition to these built-in transformations, there are two additional methods that can be modified for more thorough changes:

```python
class MyTransformer(Transformer):

    def transform(self, dic):
        """Make whatever changes needed here."""
        return dic

    def validate(self, dic):
        """Raise ValidationErrors"""
        if last_name == 'Bunny':
            raise ValidationError('I do not want to have this record')
```

Both methods will be applied after the forementioned built-in methods.


## Django form support

Django-etl-sync fully support Django forms. You can reuse the Django forms from your
project to bulk load data. See section “Transformations”.


## Create transformer for related models

## Other strategies for loading normalized or related data

### Table dumps of related tables

### Creating related tables from same data source

## File load

## Logging

Django-etl-sync will create a log file in the same location as the source file.
It will contain the list of rejected records.

```bash
source_file.txt
source_file.txt.2014-07-23.log
```


## Roadmap

- Create readers for more source types, especially for comma limited data, and headerless CSV.
- Add a way for data removal, if deleted from source.



[travis-image]: https://travis-ci.org/postfalk/django-etl-sync.svg?branch=master
[travis-link]: https://travis-ci.org/postfalk/django-etl-sync
[coveralls-image]: https://coveralls.io/repos/postfalk/django-etl-sync/badge.png?branch=master
[coveralls-link]: https://coveralls.io/r/postfalk/django-etl-sync?branch=master
