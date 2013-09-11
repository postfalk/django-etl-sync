from django.contrib.gis.db import models


class TestModelWoFk(models.Model):
    """
    Model to test simple imports (BaseInstanceGenerator)
    """
    record = models.CharField(max_length=10)
    name = models.CharField(max_length=10, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)


class Nombre(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    name = models.CharField(max_length=10)


class Numero(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    name = models.CharField(max_length=10)


class Polish(models.Model):
    record = models.CharField(max_length=10)
    ilosc = models.CharField(max_length=10)


class ElNumero(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    rec = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=10)


class TestModel(models.Model):
    """
    Model for Unit tests.
    """
    record = models.CharField(max_length=10)
    name = models.CharField(max_length=10, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    nombre = models.ForeignKey(Nombre, null=True)
    numero = models.ForeignKey(Numero)
    elnumero = models.ForeignKey(ElNumero, to_field='rec', null=True)
    related = models.ManyToManyField(Polish, null=True)
