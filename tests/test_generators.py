from __future__ import absolute_import

from django.utils import version
from django.db import IntegrityError
from django.contrib.gis.db.models import CharField
from django.core.exceptions import ValidationError
from django.test import TestCase
from tests import models
from etl_sync.generators import (
    get_unique_fields, get_unambiguous_fields, get_fields,
    BaseGenerator, InstanceGenerator, HashMixin)


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


class TestComplexModels(TestCase):
    """This test tests the model used in the file loader test."""

    def test_complex_model(self):
        models.TestModel.objects.all().delete()
        generator = InstanceGenerator(models.TestModel)
        generator.get_instance({
            'record': 1, 'name': 'eins', 'zahl': 'uno', 'numero': 'test'})

    def test_complex_dict(self):
        generator = InstanceGenerator(models.ParentModel)
        for item in range(0, 2):
            instance = generator.get_instance({
                'well_defined': {
                    'something': 'donkey', 'somenumber': 1}})
            self.assertEqual(instance.well_defined.somenumber, 1)
            self.assertEqual(instance.well_defined.something, 'donkey')
        qs = models.WellDefinedModel.objects.all()
        self.assertEqual(qs.count(), 1)
        generator.get_instance({
            'well_defined': {
                'something': 'donkey', 'somenumber': 2}})
        qs = models.WellDefinedModel.objects.all()
        self.assertEqual(qs.count(), 2)
        with self.assertRaises((ValueError, IntegrityError)):
            generator.get_instance({
               'well_defined': {
                    'something': 'horse', 'somenumber': 2,
                    'etl_create': False}})

    def test_complex_relationships(self):
        dics = [
            {'record': 40, 'numero': 'uno'},
            {'record': 40, 'numero': 'due'},
            {'record': 43, 'numero': 'tres',
                'related': [
                    {'record': '10', 'ilosc': 'jedynka zero'},
                    {'record': '21', 'ilosc': 'dwadziescia jeden'}
                ]},
            {'record': 43, 'numero': 'quattre',
                'related': [
                    {'record': '10', 'ilosc': 'jedynka zero'},
                    {'record': '21', 'ilosc': 'jeden'},
                    {'record': '19', 'ilosc': 'jeden'}
                ]},
            {'record': 43, 'zahl': None, 'numero': 'uno'},
            {'record': 43, 'zahl': None, 'numero': None},
            {'record': 43, 'numero': 'tres',
                'related': [
                    {'record': '10', 'ilosc': 'jedynka zero'},
                    {'record': '21', 'ilosc': 'dwadziescia jeden'}
                ]
                }
        ]
        for dic in dics:
            generator = InstanceGenerator(
                models.HashTestModel, persistence='record')
            generator.get_instance(dic)
        self.assertEqual(models.Polish.objects.count(), 3)


class TestForeignKeyRelations(TestCase):

    def test_fk_rejection(self):
        generator = InstanceGenerator(models.TestModel)
        generator.get_instance({
            'record': '1', 'name': 'one', 'zahl': 'eins',
            'nombre': {
                'name': 'un', 'etl_create': False},
            'numero': 'quattre'})
        self.assertEqual(generator.res, 'created')
        with self.assertRaises((ValueError, IntegrityError)):
            generator.get_instance({
                'record': '2', 'name': 'two', 'zahl': 'eins',
                'numero': {
                    'name': 'uno', 'etl_create': False}})

    def test_fk_with_rel_field_specified(self):
        generator = InstanceGenerator(
            models.TestModel, persistence=['record'])
        instance = generator.get_instance({
            'record': '1', 'name': 'one', 'zahl': 'eins', 'nombre': 'un',
            'numero': 'uno', 'elnumero': 'el uno'})
        self.assertEqual(generator.res, 'created')
        self.assertEqual(instance.elnumero.rec, 'el uno')
        instance = generator.get_instance({
            'record': '2', 'name': 'two', 'zahl': 'zwei', 'nombre': 'deux',
            'numero': 'due', 'elnumero': 'el dos'})
        self.assertEqual(generator.res, 'created')

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
        res = generator.get_instance({'fk': 1, 'name': 'ursula'})
        self.assertEqual(res.fk.name, 'test')


class TestRelations(TestCase):

    def test_rel_creation(self):
        dics = [
            {'record': '1', 'name': 'one', 'related': [
                {'record': '10', 'ilosc': 'dziesiec',
                    'persistence': 'record'},
                {'record': '20', 'ilosc': 'dwadziescia',
                    'persistence': 'record'},
                ],
                'numero': 'uno'},
            {'record': '2', 'name': 'one', 'related': [
                {'record': '10', 'ilosc': 'jedynka zero',
                    'persistence': 'record'},
                {'record': '21', 'ilosc': 'dwadziescia jeden',
                    'persistence': 'record'},
                ],
                'numero': 'tre'}]
        for dic in dics:
            generator = InstanceGenerator(models.TestModel)
            generator.get_instance(dic)
        res = models.Polish.objects.all()
        self.assertEqual(res.count(), 3)

    def test_onetoone(self):
        ins = models.Nombre.objects.create(name='un', id=1)
        dos = models.Nombre.objects.create(name='dos', id=2)
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins', 'nombre': ins,
             'numero': 'uno'},
            {'record': '2', 'name': 'two', 'zahl': 'zwei', 'nombre': 'deux',
             'numero': 'due'},
            {'record': '3', 'name': 'three', 'zahl': 'drei', 'nombre':
             {'name': 'troix'}, 'numero': 'tre'},
            {'record': '1', 'name': 'one', 'zahl': 'vier', 'nombre': 1,
             'numero': 'quattro'},
            {'record': '1', 'name': 'one again', 'zahl': 'fuenf',
             'nombre': dos, 'numero': 'cinque'},
             {'record': '4', 'name': 'four', 'zahl': 'vier', 'nombre': 1,
              'numero': 'test'},
            {'record': '5', 'name': 'six', 'zahl': 'sechs', 'numero': 2},
            {'record': '6', 'name': 'six', 'zahl': 'sechs', 'numero': '45',
             'nombre': '2'},
            {'record': '7', 'name': 'test', 'numero': '1'}
        ]
        for dic in dics:
            generator = InstanceGenerator(
                models.TestOnetoOneModel, persistence='record')
            generator.get_instance(dic)
        res = models.Nombre.objects.all()
        self.assertEqual(res.count(), 5)
        res = models.TestOnetoOneModel.objects.all()
        self.assertEqual(res.count(), 7)
        rec = res.filter(record='1')[0]
        self.assertEqual(rec.nombre.name, 'dos')
        self.assertEqual(rec.nombre.testonetoonemodel, rec)


class TestUpdate(TestCase):

    def test_update(self):
        """
        Test record update.
        """
        dic = {'record': '100', 'numero': 'cento', 'zahl': 'hundert'}
        generator = InstanceGenerator(
            models.HashTestModel, persistence='record')
        res = generator.get_instance(dic)
        self.assertEqual(res.numero.name, 'cento')
        self.assertEqual(generator.res, 'created')
        generator.get_instance(dic)
        self.assertEqual(generator.res, 'updated')
        dic = {'record': '100', 'numero': 'hundert', 'zahl': 'hundert'}
        res = generator.get_instance(dic)
        self.assertTrue(generator.res, 'updated')
        self.assertEqual(res.numero.name, 'hundert')
        dic = {'record': '101', 'name': 'test', 'zahl': 'vier'}
        res = generator.get_instance(dic)
        self.assertTrue(generator.res, 'updated')

    def test_related_update(self):
        """
        Test update of related records if parent record is
        unchanged.
        """
        dic = {'record': '1', 'name': 'John', 'lnames': [
              {'record': '1:1', 'last_name': 'Doe',
               'attribute': 'generic'},
              {'record': '1:2', 'last_name': 'Carvello',
               'attribute': 'more_fancy'}
        ]}
        InstanceGenerator(models.SomeModel, persistence='record').get_instance(dic)
        dic = {'record': '1', 'name': 'John', 'lnames': [
              {'record': '1:1', 'last_name': 'Deer',
               'attribute': 'generic'},
              {'record': '1:2', 'last_name': 'Carvello',
               'attribute': 'more_fancy'}
        ]}
        InstanceGenerator(models.SomeModel, persistence='record').get_instance(dic)
        qs = models.SomeModel.objects.all()
        self.assertEqual(qs[0].lnames.all()[0].last_name, 'Deer')


class TestRejection(TestCase):

    def test_rejection_by_field_validation(self):
        dic = {'record': '30', 'date': '3333', 'numero': 'uno'}
        generator = InstanceGenerator(models.TestModel)
        with self.assertRaises(ValidationError):
            generator.get_instance(dic)

    def test_rejection_by_db_integrity(self):
        dic = {'record': '30', 'date': '2014-01-01'}
        generator = InstanceGenerator(models.TestModel)
        with self.assertRaises(IntegrityError):
            generator.get_instance(dic)

    def test_rejection_by_missing_fk(self):
        dic = {'record': '30', 'date': '2014-01-01', 'numero': 2}
        generator = InstanceGenerator(models.TestModel)
        with self.assertRaises(ValueError):
            generator.get_instance(dic)


class TestMiscModelFunctionality(TestCase):

    # This functionality has been removed for performance reason
    # but can be easily re-instated through sub-classing.
    def __test_signals(self):
        """Test whether auto_now=True fields get updated as well."""
        models.TestModelWoFk.objects.all().delete()
        dic = {'record': '1110'}
        InstanceGenerator(
            models.TestModelWoFk, persistence='record').get_instance(dic)
        date_1 = models.TestModelWoFk.objects.filter(record='1110')[0].date
        dic = {'record': '1110', 'name': 'test'}
        InstanceGenerator(
            models.TestModelWoFk, persistence='record').get_instance(dic)
        qs = models.TestModelWoFk.objects.filter(record='1110')
        self.assertLess(date_1, qs[0].date)


class TestPreparations(TestCase):

    def test_prepare_boolean(self):
        generator = InstanceGenerator(models.SomeModel)
        tests = [
            ('0', False), ('1', True), ('false', False), ('true', True),
            ('f', False), ('t', True), (1, True), (0, False)]
        for test in tests:
            self.assertEqual(
                generator.prepare_boolean(None, test[0]), test[1])

    def test_prepare_integer(self):
        generator = InstanceGenerator(models.SomeModel)
        tests = [
            ('1', 1), ('', None), (0, 0), (1, 1), ('bla', None)]
        for test in tests:
            self.assertEqual(
                generator.prepare_integer(None, test[0]), test[1])

    def test_prepare_geometry(self):
        from django.contrib.gis.geos import GEOSGeometry
        example3d_string = (
            'MULTIPOLYGON (((2 4 5, 2 6 5, 3 3 3, 2 4 5)),'
            '((10 10 3, 11 10 4, 10 11 4, 10 10 3)))')
        geom = GEOSGeometry(example3d_string)
        generator = InstanceGenerator(models.GeometryModel)
        generator.get_instance({
            'geom2d': geom, 'geom3d': geom, 'name': 'testcase 1'})
        item = models.GeometryModel.objects.filter(name='testcase 1')[0]
        self.assertFalse(item.geom2d.hasz)
        self.assertTrue(item.geom3d.hasz)
        example2d_string = item.geom2d
        geom = GEOSGeometry(example2d_string)
        generator = InstanceGenerator(
            models.GeometryModel)
        generator.get_instance({
                'geom2d': geom, 'geom3d': geom, 'name': 'testcase 2'})
        item = models.GeometryModel.objects.filter(name='testcase 2')[0]
        self.assertFalse(item.geom2d.hasz)
        generator.get_instance({
                'geom2d': None, 'geom3d': None, 'name': 'emptytest'})
        item = models.GeometryModel.objects.filter(name='emptytest')[0]
        self.assertFalse(item.geom2d)
        self.assertFalse(item.geom3d)

    def test_prepare_date(self):
        generator = InstanceGenerator(models.DateTimeModel)
        generator.get_instance({
            'datetimenotnull': '2014-10-14', 'datetimenull': '2014-10-14'})
        self.assertTrue(generator.res, 'created')
        with self.assertRaises(ValidationError):
            generator.get_instance({
                'datetimenotnull': '', 'datetimenull': '2014-10-14'})
        generator.get_instance({
            'datetimenotnull': '2014-10-14', 'datetimenull': ''})
        self.assertEqual(generator.res, 'created')

    def test_prepare_string(self):
        generator = InstanceGenerator(models.TestModel)
        res = generator.prepare_text(CharField(max_length=4), 'test')
        self.assertEqual(res, 'test')
        res = generator.prepare_text(CharField(max_length=3), 'test')
        self.assertEqual(res, 'tes')


class TestResults(TestCase):

    def test_results(self):
        dic = {'record': 40, 'numero': 'uno'}
        generator = InstanceGenerator(
            models.HashTestModel, persistence='record')
        generator.get_instance(dic)
        self.assertEqual(generator.res, 'created')
        generator.get_instance(dic)
        self.assertEqual(generator.res, 'updated')
        dic['numero'] = 'due'
        generator.get_instance(dic)
        self.assertEqual(generator.res, 'updated')


class TestHashing(TestCase):

    class HashGenerator(HashMixin, InstanceGenerator):
        pass

    def test_hashing(self):
        generator = self.HashGenerator(models.HashTestModel)
        instance = generator.get_instance({'record': '1', 'zahl': 'alfred'})
        self.assertEqual(len(instance.md5), 32)
        self.assertEqual(generator.res, 'created')
        generator.get_instance({'zahl': 'alfred', 'record': '1'})
        self.assertEqual(generator.res, 'exists')
        generator.get_instance({'zahl': 'britta', 'record': '1'})
        self.assertEqual(generator.res, 'updated')
        generator.get_instance({'zahl': 'britta', 'record': '2'})

    def test_hashing_without_hashfield(self):
        generator = self.HashGenerator(models.TestModel)
        generator.get_instance({'record': 1, 'numero': '23'})
        self.assertEqual(generator.res, 'created')
        generator.get_instance({'record': 1, 'numero': '23'})
        self.assertEqual(generator.res, 'updated')
        generator.get_instance({'record': 2, 'numero': '22'})
        self.assertEqual(generator.res, 'created')
