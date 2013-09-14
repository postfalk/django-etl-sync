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
    name = models.CharField(max_length=10)


class TestModel(models.Model):
    """
    Model for Unit tests.
    """
    record = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=10, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    nombre = models.ForeignKey(Nombre, null=True)
    numero = models.ForeignKey(Numero)
    elnumero = models.ForeignKey(ElNumero, to_field='rec', null=True)
    related = models.ManyToManyField(Polish, null=True)
    date = models.DateTimeField(null=True)


class HashTestModel(models.Model):
    record = models.CharField(max_length=10)
    numero = models.ForeignKey(Numero)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    related = models.ManyToManyField(Polish, null=True)
    md5 = models.CharField(max_length=30, null=True)
