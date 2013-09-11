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

2. The app provides two ways of access: file level and record level load.

3. Minimal example: File level load::


.. code-block:: python
  class test
  
and

.. code-block:: python
  
  # models.py
  from django.db import models
  
  class TestModel(models.Model)
  """
  Example Model.
  """
  record = models.CharField(max_length=10)
  name = models.CharField(max_length=10, null=True, blank=True)

  


Next Steps
----------

- Create readers for more source types, especially for comma limited data, and headerless CSV.
- Add a way for data removal, if deleted from source.
- Improve logging.
- Form support
