# Django ETL Sync

ETL based on Django model introspection

[![Build Status][travis-image]][travis-link]
[![Coverage Status][coveralls-image]][coveralls-link]

---

## Overview

This reusable app is an ETL module that is not geared toward speed but toward syncing 
data sources (e.g. for an API). Data persistence as well as data normalization were the main concerns. 

The module derives ETL rules by inspecting Django Models. This rules can be modified and overriden.

The transformation process generates a dictionary matching destination model fields.

## How to use

### Installation

The package is in active development toward a release. For evaluation, 
contributions, and testing. 

```bash
    pip install -e git+ssh://git@github.com/postfalk/django-etl-sync#egg=django-etl-sync 
````

Add `etl_sync` to `INSTALLED_APPS` in settings.py.

### Minimal Examples

The app provides two ways of access: file level and record level.

#### Minimal example: File level load:

```python
  # data.txt
  record  name
  1 one
  2 two
  3 three


  # models.py
  from django.db import models
  
  class TestModel(models.Model)
  """
  Example Model.
  """
  record = models.CharField(max_length=10)
  name = models.CharField(max_length=10, null=True, blank=True)
  
  
  # <yourscript>.py
  from etl_sync.mappers import Mapper
  from <yourproject>.models import TestModel
  
  class YourMapper(Mapper)
    """
    Add your specific settings here.
    """
    filename = 'data.txt'
    model_class = TestModel
  
  mapper = YourMapper
  res = mapper.load()
```
  

#### Minimal example: dictionary load


```python

  # <yourscript>.py
  from etl_sync.generators import BaseInstanceGenerator
  from <yourproject>.models import TestModel
  
  dic = {'record': 3, 'name': 'three'}
  
  generator = BaseInstanceGenerator(TestModel, dic)
  instance = generator.get_instance()
  print(instance, generator.res)
```


### Persistence

For sync'ing the data it is essential to identify whether a record already exists, and whether it needs to be modified or added.

For more sophisticated ETL tasks use the class **InstanceGenerator** which provides persistence checks as well as generation of related instances such as foreign keys and many-to-many relationships.

**Unique fields**

Before loading a record it might be necessary to check whether the record already exists, whether it needs to be added or updated (persistence). 
By default the module inspects the target model and uses fields with the **model field** attribute unique=True as criterion for persistence. The module will check
first whether any record with this combination of values already exists and update that record. 

The id field is excluded from this check. Do not use the model internal pk field as identifier for your data! Add an extra record field.

**Extra arguments**

Another method to add (or overwrite) persistence criterions is to add a a list of fields via key word argument. 

```python
    generator = InstanceGenerator(TestModel, dic, persistence = ['record', 'source'])
```
    

**Subclassing**

You can also subclass InstanceGenerator to create your own generator class.

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

This technique is useful for nested records if the recursive call of InstanceGenerator cannot be 
directly accessed (see below). However ...

**Defining persistence by a field attributes and a concise data model is the preferred method.**

Once the variable **persistence** is overwritten the model field attributes will be ignored. Nevertheless,
conflicts with your data definition will through database errors.

## Transformations

Transformations remap the dictionary from the CSV reader or 
another reader class to the Django model. We attempt to map the 
dictionary key to the model field with the matching name. 
The transformer classes allow for remapping and validation of incoming
records.

Instantiate InstanceGenerator with a costumized Transformer class:

```python
    from etl_sync.generators import InstanceGenerator
    from etl_sync.transformes import Transformer

    class MyTransformer(Transformer):
        mappings = {“id”: “record”, “name”: “last_name”}
        defaults = {“last_name”: “Doe”}
        forms = []
        blacklist = {“last_name”: [“NA”, r”unknown”]}

    class MyInstanceGenerator(InstanceGenerator):
        transformer_class = MyTransformer
```

There are a couple of things going on here:

* The `mapping` property contains a dictionary in the form `{‘original_fieldname’: ‘new_fieldname’}` which will remap the dictionary.
* The `defaults` property holds a dictionary that gets applied if the value for the dictionary key in question is empty.
* The `forms` property holds a list of Django forms that get applied to the dictionary. WARNING: old values will not be removed. The cleaned_data keys will be added to the dictionary.
* And finally the `blacklist` property holds a list of values for each keys that will be rendered invalid.

WARNING: These methods will be applied in exactly that order. If the dictionary changes in one of these steps, the next step needs to take these changes into consideration.

In addition to these built-in transformations, there are two additional methods that can be modified for more thorough changes:

```python
    class MyTransformer(Transformer):

    def transform(self, dic):
        “””Make whatever changes needed here.”””
        return dic

    def validate(self, dic):
        “””Raise ValidationErrors”””
        if last_name == “Bunny”:
            raise ValidationError(“I do not want to have this record”) 
```

Both methods will be applied after the forms and before the blacklist.


## Roadmap

- Create readers for more source types, especially for comma limited data, and headerless CSV.
- Add a way for data removal, if deleted from source.
- Improve logging.
- Form support



[travis-image]: https://travis-ci.org/postfalk/django-etl-sync.svg?branch=master
[travis-link]: https://travis-ci.org/postfalk/django-etl-sync
[coveralls-image]: https://coveralls.io/repos/postfalk/django-etl-sync/badge.png?branch=master
[coveralls-link]: https://coveralls.io/r/postfalk/django-etl-sync?branch=master
