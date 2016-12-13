from __future__ import absolute_import

from django.utils import version
from django.core.exceptions import ValidationError
from unittest import TestCase
from tests import models
from etl_sync.generators import (
    get_unique_fields, get_unambiguous_fields, get_fields,
    BaseGenerator, InstanceGenerator)


VERSION = version.get_version()[2]


class TestUtils(TestCase):

    def test_get_unique_fields(self):
        self.assertEqual(
            get_unique_fields(models.Polish), ['record'])
        self.assertEqual(get_unique_fields(models.TwoUnique),
            ['record', 'anotherfield'])

    def test_get_unambigous_fields(self):
        results = [
            (models.TestModelWoFk, []),
            (models.Nombre, ['name']),
            (models.Polish, ['record']),
            (models.WellDefinedModel, ['something', 'somenumber'])
        ]
        for item in results:
            self.assertEqual(
                get_unambiguous_fields(item[0]), item[1])
        with self.assertRaises(ValidationError):
            get_unambiguous_fields(models.TwoUnique)

    def test_get_fields(self):
        length = len(get_fields(models.SomeModel))
        if VERSION == '7':
            self.assertEqual(length, 4)
        else:
            self.assertEqual(length, 5)


class TestBaseGenerator(TestCase):

    def test_instance_generation(self):
        generator = BaseGenerator(models.TestModelWoFk)
        res = generator.get_instance({
            'record': '1', 'name': 'test', 'zahl': '1'})
        self.assertIsInstance(res, models.TestModelWoFk)
        self.assertEqual(res.record, '1')
        self.assertEqual(res.name, 'test')
        self.assertEqual(res.zahl, '1')


class TestInstanceGenerator(TestCase):

    def test_instance_generation(self):
        generator = InstanceGenerator(models.TestModelWoFk)
        res = generator.get_instance({
            'record': 1, 'name': 'test', 'zahl': '1'})
        self.assertIsInstance(res, models.TestModelWoFk)
        self.assertEqual(res.record, '1')
        self.assertEqual(res.name, 'test')
        self.assertEqual(res.zahl, '1')

    def test_fk_model(self):
        generator = InstanceGenerator(models.SimpleFkModel)
        res = generator.get_instance({
            'fk': {
                'name': 'test'},
            'name': 'britta'})
        self.assertIsInstance(res, models.SimpleFkModel)
        self.assertIsInstance(res.fk, models.Nombre)
        self.assertEqual(res.fk.name, 'test')
        res = generator.get_instance({
            'fk': {
                'name': 'test'},
            'name': 'ulf'})
        obj_pk = models.Nombre.objects.get(name='test').pk
        res = generator.get_instance({'fk': 1, 'name': 'ursula'})
        self.assertEqual(res.fk.name, 'test')


class TestComplexModel(TestCase):
    """This test tests the model used in the file loader test."""

    def test_complex_model(self):
        generator = InstanceGenerator(models.TestModel)
        generator.get_instance({
            'record': 1, 'name': 'eins', 'zahl': 'uno'})
