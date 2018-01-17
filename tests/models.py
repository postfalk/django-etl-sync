from django.contrib.gis.db import models


class TestModelWoFk(models.Model):
    """
    Model to test simple imports (BaseInstanceGenerator)
    """
    record = models.CharField(max_length=10)
    name = models.CharField(max_length=10, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    date = models.DateTimeField(auto_now=True)


class Nombre(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    name = models.CharField(max_length=10, blank=True, unique=True)


class SimpleFkModel(models.Model):
    fk = models.ForeignKey(Nombre, on_delete=models.CASCADE)
    name = models.CharField(max_length=10)


class Numero(models.Model):
    """
    ForeignKey Model for unit tests.
    """
    name = models.CharField(max_length=10, unique=True)

    def __unicode__(self):
        return self.name


class Polish(models.Model):
    record = models.CharField(max_length=10, unique=True)
    ilosc = models.CharField(max_length=10)

    def __unicode__(self):
        return self.ilosc


class ElNumero(models.Model):
    """
    Foreign key Model for unit tests.
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
    nombre = models.ForeignKey(Nombre, null=True, on_delete=models.CASCADE)
    numero = models.ForeignKey(Numero, on_delete=models.CASCADE)
    elnumero = models.ForeignKey(
        ElNumero, to_field='rec', null=True, blank=True,
        on_delete=models.CASCADE)
    related = models.ManyToManyField(Polish, blank=True)
    date = models.DateTimeField(null=True, blank=True)


class TestOnetoOneModel(models.Model):
    """
    Model for Unit tests.
    """
    record = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=10, null=True, blank=True)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    nombre = models.OneToOneField(
        Nombre, null=True, blank=True, on_delete=models.CASCADE)
    numero = models.ForeignKey(Numero, on_delete=models.CASCADE)
    elnumero = models.ForeignKey(
        ElNumero, to_field='rec', null=True, blank=True,
        on_delete=models.CASCADE)
    related = models.ManyToManyField(Polish, blank=True)
    date = models.DateTimeField(null=True, blank=True)


class HashTestModel(models.Model):
    record = models.CharField(max_length=10, unique=True)
    numero = models.ForeignKey(
        Numero, null=True, blank=True, on_delete=models.CASCADE)
    zahl = models.CharField(max_length=10, null=True, blank=True)
    related = models.ManyToManyField(Polish)
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
    somemodel = models.ForeignKey(SomeModel, on_delete=models.CASCADE)
    anothermodel = models.ForeignKey(AnotherModel, on_delete=models.CASCADE)
    attribute = models.CharField(max_length=10, blank=True)


class GeometryModel(models.Model):
    name = models.CharField(max_length=10, null=True, blank=True)
    geom2d = models.GeometryField(null=True, blank=True)
    geom3d = models.GeometryField(null=True, blank=True, dim=3)
    # objects = models.GeoManager()


class DateTimeModel(models.Model):
    datetimenotnull = models.DateTimeField()
    datetimenull = models.DateTimeField(null=True, blank=True)


class WellDefinedModel(models.Model):
    something = models.CharField(max_length=20)
    somenumber = models.IntegerField()

    class Meta:
        unique_together = ('something', 'somenumber')


class ParentModel(models.Model):
    well_defined = models.ForeignKey(
        WellDefinedModel, on_delete=models.CASCADE)


class TwoUnique(models.Model):
    record = models.CharField(max_length=2, unique=True)
    anotherfield = models.CharField(max_length=2, unique=True)


class TwoRelatedAsUnique(models.Model):
    numero = models.ForeignKey(Numero, on_delete=models.CASCADE)
    another = models.ForeignKey(AnotherModel, on_delete=models.CASCADE)
    value = models.CharField(max_length=5)

    class Meta:
        unique_together = ('numero', 'another')

class RelatedRelated(models.Model):
    key = models.ForeignKey(TwoRelatedAsUnique, on_delete=models.CASCADE)
    value = models.CharField(max_length=5)
