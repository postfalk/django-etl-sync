from django.contrib.gis.db import models


class TestModel(models.Model):
    """
    Model for module unit tests.
    """
    record = models.CharField(max_length=10)
    name = models.CharField(max_length=10, null=True, blank=True)
