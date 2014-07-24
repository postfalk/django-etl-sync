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
    name = models.CharField(max_length=10, blank=True)


class Numero(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    name = models.CharField(max_length=10)

    def __unicode__(self):
        return self.name


class Polish(models.Model):
    record = models.CharField(max_length=10, unique=True)
    ilosc = models.CharField(max_length=10)

    def __unicode__(self):
        return self.ilosc


class ElNumero(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    rec = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=10, blank=True)
    nochwas = models.CharField(max_length=2, blank=True)


class TestModel(models.Model):
    """
    Model for Unit tests.
    """
    record = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=10, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    nombre = models.ForeignKey(Nombre, null=True, blank=True)
    numero = models.ForeignKey(Numero)
    elnumero = models.ForeignKey(
        ElNumero, to_field='rec', null=True, blank=True)
    related = models.ManyToManyField(Polish, null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)


class HashTestModel(models.Model):
    record = models.CharField(max_length=10)
    numero = models.ForeignKey(Numero, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    related = models.ManyToManyField(Polish, null=True)
    md5 = models.CharField(max_length=32, null=True)


class AnotherModel(models.Model):
    record = models.CharField(max_length=10, unique=True)
    last_name = models.CharField(max_length=10, blank=True)


class SomeModel(models.Model):
    record = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=10, blank=True)
    lnames = models.ManyToManyField(
        AnotherModel, through='IntermediateModel')


class IntermediateModel(models.Model):
    somemodel = models.ForeignKey(SomeModel)
    anothermodel = models.ForeignKey(AnotherModel)
    attribute = models.CharField(max_length=10, blank=True)
