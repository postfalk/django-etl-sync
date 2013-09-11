===============
Django ETL Sync
===============

This reusable app is an ETL module that is not necessarily geared toward speed but toward syncing 
a data source e.g. in an API. For this reason, data persistence and support for data normalization 
where the main concerns. 

The module tries to derive ETL rules by Django Model inspection. Additional rules can be added.

How to use
----------

1. Add etl_sync to your installed apps.

2. Minimal example::
  
  class Test:
    test


Next Steps
----------

- Create readers for more source types, especially for comma limited data, and headerless CSV.
- Add a way for data removal, if deleted from source.
- Improve logging.
