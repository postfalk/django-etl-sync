===============
Django ETL Sync
===============

This reusable app is an ETL module that is not necessarily geared toward speed but toward syncing 
a data source e.g. in an API. For this reason, data persistence, and support for data normalization 
are the main concerns. 

The module tries to derive ETL rules by inspection the Django Model in which the data will be loaded. 
Additional rules can be added to the transform method.

How to use
----------

1. Add etl_sync to your installed apps.

2. The app provides two ways of access: file level and record level.

3. Minimal example: File level load:


.. code-block:: text
  
  # data.txt (tab-delimited)
  record  name
  1 one
  2 two
  3 three


.. code-block:: python
  
  # models.py
  from django.db import models
  
  class TestModel(models.Model)
  """
  Example Model.
  """
  record = models.CharField(max_length=10)
  name = models.CharField(max_length=10, null=True, blank=True)
  
  
.. code-block:: python

  # <yourscript>.py
  from etl_sync.mappers import Mapper
  from <yourproject>.models import Models
  
  class YourMapper(Mapper)
    """
    Add your specific settings here.
    """
    filename = 'data.txt'
    model_class = TestModel
  
  mapper = YourMapper
  res = mapper.load()
  

4. Minimal example for dictionary load


.. code-block:: python

  # <yourscript>.py
  from etl_sync.generators import BaseInstanceGenerator
  from <yourproject>.models import Models
  
  dic = {'record': 3, 'name': 'three'}
  
  generator = BaseInstanceGenerator(TestModel, dic)
  generator.get_instance()
  print(generator.res)


Next Steps
----------

- Create readers for more source types, especially for comma limited data, and headerless CSV.
- Add a way for data removal, if deleted from source.
- Improve logging.
- Form support
