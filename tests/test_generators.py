from __future__ import absolute_import

from django.utils import version
from django.core.exceptions import ValidationError
from unittest import TestCase
from tests import models
from etl_sync.generators import (
    get_unique_fields, get_unambiguous_fields, get_fields)


VERSION = version.get_version()[2]

class TestUtils(TestCase):

    def test_get_unique_fields(self):
        self.assertEqual(
            get_unique_fields(models.Polish), ['record'])
        self.assertEqual(get_unique_fields(models.TwoUnique),
            ['record', 'anotherfield'])

    def test_get_unambigous_fields(self):
        for item in [
            models.ElNumero, models.Nombre, models.TestModel,
            models.TestModelWoFk, models.Numero, models.SomeModel,
            models.GeometryModel, models.TestOnetoOneModel
        ]:
            self.assertEqual(get_unambiguous_fields(item), ['name'])
        for item in [models.Polish, models.AnotherModel]:
            self.assertEqual(get_unambiguous_fields(item), ['record'])
        self.assertEqual(
            get_unambiguous_fields(models.IntermediateModel), ['attribute'])
        self.assertEqual(
            get_unambiguous_fields(models.WellDefinedModel),
            ['something', 'somenumber'])
        with self.assertRaises(ValidationError):
            get_unambiguous_fields(models.HashTestModel)

    def test_get_fields(self):
        length = len(get_fields(models.SomeModel))
        if VERSION == '7':
            self.assertEqual(length, 4)
        else:
            self.assertEqual(length, 5)

