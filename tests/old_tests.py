# Python 3.x compatibility
from __future__ import absolute_import
from six import text_type
from future.utils import iteritems

import warnings

from django.db import transaction
import os
import glob
from io import StringIO
from django.test import TestCase
from django.core.exceptions import ValidationError
from tests.models import (
    ElNumero, HashTestModel, Nombre, Polish, TestModel, TestModelWoFk,
    SomeModel, AnotherModel, IntermediateModel, GeometryModel,
    DateTimeModel, TestOnetoOneModel, WellDefinedModel, ParentModel)
from etl_sync.generators import (
    BaseInstanceGenerator, InstanceGenerator)
from etl_sync.mappers import Mapper
from etl_sync.loaders import Loader, Extractor, FeedbackCounter
from etl_sync.readers import unicode_dic, ShapefileReader, OGRReader
from etl_sync.transformations import Transformer


warnings.simplefilter('always', DeprecationWarning)


class TestModule(TestCase):

    def test_test_db(self):
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins'},
            {'record': '2', 'name': 'two', 'zahl': 'zwei'},
            {'record': '3', 'name': 'three', 'zahl': 'drei'},
            {'record': '1', 'name': 'one', 'zahl': 'vier'},
            {'record': '1', 'name': 'one again'},
            {'record': '2', 'zahl': None}
        ]
        # test without persistence criterion
        for dic in dics:
            BaseInstanceGenerator(TestModelWoFk).get_instance(dic)
        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 6)
        self.assertEqual(res.filter(record='1')[0].name, 'one')
        res.delete()
        # test with persistence criterion
        for dic in dics:
            BaseInstanceGenerator(
                TestModelWoFk, persistence='record').get_instance(dic)
        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 3)
        self.assertEqual(res.filter(record='1')[0].name, 'one again')
        self.assertEqual(res.filter(record='1')[0].zahl, 'vier')
        self.assertEqual(res.filter(record='2')[0].zahl, None)
        res.delete()
        # test with double persistence criterion
        for dic in dics:
            generator = BaseInstanceGenerator(
                TestModelWoFk, persistence=['record', 'name'])
            generator.get_instance(dic)
        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 4)
        self.assertEqual(res.filter(record='1')[0].zahl, 'vier')
        res.delete()

    def test_fk(self):
        ins = Nombre(name='un')
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
             'nombre': 'quatre', 'numero': 'cinque'},
            {'record': '4', 'name': 'four', 'zahl': 'vier', 'nombre': 1,
             'numero': 'test'},
            {'record': '5', 'name': 'six', 'zahl': 'sechs', 'numero': 2},
            {'record': '6', 'name': 'six', 'zahl': 'sechs', 'numero': '45',
             'nombre': '2'},
            {'record': '7', 'name': 'test', 'numero': '1'}
        ]
        for dic in dics:
            generator = InstanceGenerator(
                TestModel, persistence='record')
            generator.get_instance(dic)
        res = Nombre.objects.all()
        self.assertEqual(res.count(), 5)
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 7)
        self.assertEqual(res.filter(record='1')[0].nombre.name, 'quatre')
        res.delete()

    def test_fk_rejection(self):
        dics = [
            # nombre example with fk that allows None
            {'record': '1', 'name': 'one', 'zahl': 'eins',
                'nombre': {'name': 'un', 'etl_create': False},
             'numero': 'quattre', 'expect': True},
            # numero example with fk that does not allow None
            {'record': '2', 'name': 'two', 'zahl': 'eins',
                'numero': {'name': 'uno', 'etl_create': False},
             'expect': False}
        ]
        for dic in dics:
            generator = InstanceGenerator(TestModel, persistence='record')
            if dic['expect']:
                generator.get_instance(dic)
            else:
                with self.assertRaises(ValidationError):
                    generator.get_instance(dic)
            result = generator.res
        self.assertEqual(result['created'], False)
        self.assertEqual(result['updated'], False)
        self.assertEqual(Nombre.objects.all().count(), 0)
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 1)
        self.assertEqual(res[0].nombre, None)

    def test_fk_with_rel_field_specified(self):
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins', 'nombre': 'un',
                'numero': 'uno', 'elnumero': 'el uno'},
            {'record': '2', 'name': 'two', 'zahl': 'zwei', 'nombre': 'deux',
                'numero': 'due', 'elnumero': 'el dos'},
            {'record': '3', 'name': 'three', 'zahl': 'drei',
                'nombre': {'name': 'troix'}, 'numero': 'tre',
                'elnumero': 'el tres'},
            {'record': '1', 'name': 'one', 'zahl': 'vier', 'nombre': 1,
                'numero': 'quattro', 'elnumero': 'el tres'},
            {'record': '1', 'name': 'one again', 'zahl': 'fuenf',
                'nombre': 'quatre', 'numero': 'cinque'},
        ]
        for dic in dics:
            generator = InstanceGenerator(
                TestModel, persistence='record')
            generator.get_instance(dic)
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 3)
        self.assertEqual(res[0].elnumero_id, 'el tres')
        res = ElNumero.objects.all()
        self.assertEqual(res.count(), 3)

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
            generator = InstanceGenerator(
                TestModel, persistence='record')
            generator.get_instance(dic)
        res = Polish.objects.all()
        self.assertEqual(res.count(), 3)
        # tests also field truncation
        self.assertEqual(res.filter(record='10')[0].ilosc, 'jedynka ze')
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 2)
        self.assertEqual(len(res.filter(record='1')[0].related.values()), 2)

    def test_onetoone(self):
        ins = Nombre.objects.create(name='un', id=1)
        dos = Nombre.objects.create(name='dos', id=2)
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
        with transaction.atomic():
            for dic in dics:
                generator = InstanceGenerator(
                    TestOnetoOneModel, persistence='record')
                generator.get_instance(dic)
            res = Nombre.objects.all()
            self.assertEqual(res.count(), 5)
            res = TestOnetoOneModel.objects.all()
            self.assertEqual(res.count(), 7)
            rec1 = res.filter(record='1')[0]
            self.assertEqual(rec1.nombre.name, 'dos')
            self.assertEqual(rec1.nombre.testonetoonemodel, rec1)
            res.delete()

    def test_validation(self):
        dics = [{'record': '30', 'date': '3333', 'numero': 'uno'}]
        for dic in dics:
            generator = InstanceGenerator(TestModel, persistence='record')
            with self.assertRaises(ValidationError):
                generator.get_instance(dic)

    def test_hashing(self):
        dics = [
            {'record': 40, 'numero': 'uno'},
            {'record': 40, 'numero': 'due'},
            {'record': 43, 'numero': 'tres',
                'related': [
                    {'record': '10', 'ilosc': 'jedynka zero',
                        'persistence': 'record'},
                    {'record': '21', 'ilosc': 'dwadziescia jeden',
                        'persistence': 'record'},
                ]},
            {'record': 43, 'numero': 'quattre',
                'related': [
                    {'record': '10', 'ilosc': 'jedynka zero',
                        'persistence': 'record'},
                    {'record': '21', 'ilosc': 'jeden',
                        'persistence': 'record'},
                    {'record': '19', 'ilosc': 'jeden',
                        'persistence': 'record'},
                ]},
            {'record': 43, 'zahl': None, 'numero': 'uno'}]
        for dic in dics:
            generator = InstanceGenerator(
                HashTestModel, persistence='record')
            try:
                generator.get_instance(dic)
            except:
                pass
        res = HashTestModel.objects.all()
        self.assertEqual(res.count(), 2)
        self.assertEqual(res.filter(record='40')[0].numero.name, 'due')
        self.assertNotEqual(res[0].md5, res[1].md5)
        self.assertEqual(res.get(record='43').related.all().count(), 3)

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
                InstanceGenerator(
                    HashTestModel, persistence='record').get_instance(dic)
            self.assertEqual(Polish.objects.count(), 3)

    def assertResult(self, res, expected):
        self.assertEqual(res['updated'], expected[0])
        self.assertEqual(res['exists'], expected[1])
        self.assertEqual(res['created'], expected[2])

    def test_results(self):
        dic = {'record': 40, 'numero': 'uno'}
        generator = InstanceGenerator(HashTestModel, persistence='record')
        generator.get_instance(dic)
        self.assertResult(generator.res, (False, False, True))
        generator.get_instance(dic)
        self.assertResult(generator.res, (False, True, False))
        generator.get_instance(dic)
        self.assertResult(generator.res, (False, True, False))
        dic['numero'] = 'due'
        generator.get_instance(dic)
        self.assertResult(generator.res, (True, True, False))

    def test_md5(self):
        dics = [{'record': 43, 'numero': 'due'},
                {'record': 43, 'numero': 'due'},
                {'record': 43, 'numero': 'tres'}]
        generator = InstanceGenerator(
            HashTestModel, persistence='record')
        instance = generator.get_instance(dics[0])
        hashvalue1 = instance.md5
        generator = InstanceGenerator(
            HashTestModel, persistence='record')
        instance = generator.get_instance(dics[1])
        self.assertEqual(hashvalue1, instance.md5)
        generator = InstanceGenerator(
            HashTestModel, persistence='record')
        instance = generator.get_instance(dics[2])
        self.assertNotEqual(hashvalue1, instance.md5)
        res = HashTestModel.objects.filter(record=43)
        self.assertNotEqual(hashvalue1, res[0].md5)


class TestLoad(TestCase):
    """
    Tests data loading from file.
    """

    def tearDown(self):
        path = os.path.dirname(os.path.realpath(__file__))
        files = glob.glob('%s/data.txt.*.log' % path)
        (os.remove(fil) for fil in files)

    def test_load_from_file(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            path = os.path.dirname(os.path.realpath(__file__))
            filename = '{0}/data.txt'.format(path)
            mapper = Mapper(filename=filename, model_class=TestModel)
            mapper.load()
            self.assertEqual(TestModel.objects.all().count(), 3)


class TestReaders(TestCase):
    """
    Test readers, encoding problems in particular.
    """

    def setUp(self):
        path = os.path.dirname(os.path.realpath(__file__))
        self.testfilename = os.path.join(path, 'test_shapefile.shp')

    def test_dic_decoder(self):
        testdic = {
            'word': b'testword', 'number': 68898, 'utf8': b'testing\xc2\xa0'}
        dic = unicode_dic(testdic, 'utf-8')
        self.assertEqual(dic['utf8'], u'testing\xa0')
        for k, v in iteritems(dic):
            self.assertIsInstance(k, text_type)

    def test_ogr_reader(self):
        reader = OGRReader(self.testfilename)
        dic = reader.next()
        self.assertEqual(dic['text'], u'three')
        dic = reader.next()
        self.assertEqual(dic['text'], u'two')


    def test_deprecated_shapefile_readr(self):
        with warnings.catch_warnings(record=True) as w:
            reader = ShapefileReader(self.testfilename)
            self.assertEqual(w[-1].category, DeprecationWarning)
            dic = reader.next()
            self.assertEqual(dic['text'], u'three')
            dic = reader.next()
            self.assertEqual(dic['text'], u'two')


class TestTransformer(TestCase):

    def helper(self, transformer):
        transformer.cleaned_data

    def test_base_transformer(self):
        dic = {'test1': 'testus', 'test2': 'testus testus'}
        transformer = Transformer(dic)
        self.assertRaises(AttributeError, self.helper, transformer)
        self.assertTrue(transformer.is_valid())
        self.assertEqual(transformer.cleaned_data['test1'], 'testus')
        self.assertEqual(transformer.cleaned_data['test2'], 'testus testus')

    def test_remap(self):
        dic = {
            'TEST': 'test', 'another_field': 'content', 'third_field': 'text'}
        transformer = Transformer(dic)
        transformer.mappings = {'test': 'TEST', 'field': 'another_field'}
        self.assertTrue(transformer.is_valid())
        res = transformer.cleaned_data
        self.assertEqual(res['test'], 'test')
        self.assertEqual(res['field'], 'content')
        self.assertEqual(res['third_field'], 'text')
        self.assertNotIn('TEST', res)
        self.assertNotIn('another_field', res)

    def test_blacklist(self):
        dic = {'test': 'something', 'another_field': 'rubish and something'}
        transformer = Transformer(dic)
        transformer.blacklist = {'another_field': [r'^rubish']}
        self.assertFalse(transformer.is_valid())


class TestM2MWithThrough(TestCase):

    def test_through(self):
        """Test M2M with through model."""
        dic = {'record': '1', 'name': 'John', 'lnames': [
              {'record': '1:1', 'last_name': 'Doe',
               'attribute': 'generic'},
              {'record': '1:2', 'last_name': 'Carvello',
               'attribute': 'more_fancy'}
        ]}
        generator = InstanceGenerator(SomeModel, persistence='record')
        generator.get_instance(dic)
        qs = SomeModel.objects.all()
        self.assertEqual(qs[0].record, '1')
        self.assertEqual(qs[0].name, 'John')
        self.assertEqual(qs[0].lnames.all()[0].last_name, 'Doe')
        qs = AnotherModel.objects.all()
        self.assertEqual(qs.count(), 2)
        self.assertEqual(qs[0].record, '1:1')
        self.assertEqual(qs[1].record, '1:2')
        qs = IntermediateModel.objects.all()
        self.assertEqual(qs[0].attribute, 'generic')
        self.assertEqual(qs[1].attribute, 'more_fancy')


class TestUpdate(TestCase):

    def test_update(self):
        """
        Test record update.
        """
        dic = {'record': '100', 'numero': 'cento', 'zahl': 'hundert'}
        generator = InstanceGenerator(
            HashTestModel, persistence='record')
        res = generator.get_instance(dic)
        self.assertEqual(res.numero.name, 'cento')
        self.assertTrue(generator.res['created'])
        self.assertFalse(generator.res['updated'])
        generator.get_instance(dic)
        self.assertFalse(generator.res['created'])
        self.assertFalse(generator.res['updated'])
        self.assertTrue(generator.res['exists'])
        dic = {'record': '100', 'numero': 'hundert', 'zahl': 'hundert'}
        generator = InstanceGenerator(
            HashTestModel, persistence='record')
        res = generator.get_instance(dic)
        self.assertTrue(generator.res['updated'])
        self.assertEqual(res.numero.name, 'hundert')
        dic = {'record': '101', 'name': 'test', 'zahl': 'vier'}
        generator = InstanceGenerator(
            TestModelWoFk, persistence='record')
        res = generator.get_instance(dic)
        res = generator.get_instance(dic)
        self.assertTrue(generator.res['updated'])

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
        InstanceGenerator(SomeModel, persistence='record').get_instance(dic)
        dic = {'record': '1', 'name': 'John', 'lnames': [
              {'record': '1:1', 'last_name': 'Deer',
               'attribute': 'generic'},
              {'record': '1:2', 'last_name': 'Carvello',
               'attribute': 'more_fancy'}
        ]}
        InstanceGenerator(SomeModel, persistence='record').get_instance(dic)
        qs = SomeModel.objects.all()
        self.assertEqual(qs[0].lnames.all()[0].last_name, 'Deer')

    def test_signals(self):
        """Test whether auto_now=True fields get updated as well."""
        dic = {'record': '1110'}
        InstanceGenerator(
            TestModelWoFk, persistence='record').get_instance(dic)
        date_1 = TestModelWoFk.objects.filter(record='1110')[0].date
        dic = {'record': '1110', 'name': 'test'}
        InstanceGenerator(
            TestModelWoFk, persistence='record').get_instance(dic)
        qs = TestModelWoFk.objects.filter(record='1110')
        self.assertLess(date_1, qs[0].date)


class TestPreparations(TestCase):

    def test_prepare_boolean(self):
        generator = InstanceGenerator(SomeModel)
        tests = [
            ('0', False), ('1', True), ('false', False), ('true', True),
            ('f', False), ('t', True), (1, True), (0, False)]
        for test in tests:
            self.assertEqual(
                generator._prepare_boolean(None, test[0]), test[1])

    def test_prepare_integer(self):
        generator = InstanceGenerator(SomeModel)
        tests = [
            ('1', 1), ('', None), (0, 0), (1, 1), ('bla', None)]
        for test in tests:
            self.assertEqual(
                generator._prepare_integer(None, test[0]), test[1])

    def test_prepare_geometry(self):
        from django.contrib.gis.geos import GEOSGeometry
        example3d_string = (
            'MULTIPOLYGON (((2 4 5, 2 6 5, 3 3 3, 2 4 5)),'
            '((10 10 3, 11 10 4, 10 11 4, 10 10 3)))')
        geom = GEOSGeometry(example3d_string)
        generator = InstanceGenerator(
            GeometryModel)
        generator.get_instance(
            {'geom2d': geom, 'geom3d': geom, 'name': 'testcase 1'})
        item = GeometryModel.objects.filter(name='testcase 1')[0]
        self.assertFalse(item.geom2d.hasz)
        self.assertTrue(item.geom3d.hasz)
        example2d_string = item.geom2d
        geom = GEOSGeometry(example2d_string)
        generator = InstanceGenerator(
            GeometryModel).get_instance(
                {'geom2d': geom, 'geom3d': geom,
                 'name': 'testcase 2'})
        item = GeometryModel.objects.filter(name='testcase 2')[0]
        self.assertFalse(item.geom2d.hasz)
        generator = InstanceGenerator(
            GeometryModel).get_instance({'geom2d': None, 'geom3d': None,
                            'name': 'emptytest'})
        item = GeometryModel.objects.filter(name='emptytest')[0]
        self.assertFalse(item.geom2d)
        self.assertFalse(item.geom3d)

    def test_prepare_date(self):
        generator = InstanceGenerator(DateTimeModel)
        generator.get_instance({
            'datetimenotnull': '2014-10-14', 'datetimenull': '2014-10-14'})
        self.assertTrue(generator.res['created'])
        with self.assertRaises(ValidationError):
            generator.get_instance({
                'datetimenotnull': '', 'datetimenull': '2014-10-14'})
        generator.get_instance({
            'datetimenotnull': '2014-10-14', 'datetimenull': ''})
        self.assertTrue(generator.res['created'])


class TestDictAsForeignKey(TestCase):

    def test_complex_dict(self):
        generator = InstanceGenerator(ParentModel)
        for item in range(0, 2):
            instance = generator.get_instance({
                'well_defined': {
                    'something': 'donkey', 'somenumber': 1}})
            self.assertEqual(instance.well_defined.somenumber, 1)
            self.assertEqual(instance.well_defined.something, 'donkey')
        qs = WellDefinedModel.objects.all()
        self.assertEqual(qs.count(), 1)
        generator.get_instance({
            'well_defined': {
                'something': 'donkey', 'somenumber': 2}})
        qs = WellDefinedModel.objects.all()
        self.assertEqual(qs.count(), 2)
        with self.assertRaises(ValidationError):
           generator.get_instance({
               'well_defined': {
                    'something': 'horse', 'somenumber': 2,
                    'etl_create': False}})


class TestExtractor(TestCase):
    """Test newly introduced ExtractorClass."""

    def setUp(self):
        self.filename = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'data.txt')

    def test_fileload(self):
        extractor = Extractor(self.filename)
        with extractor as ex:
            ct = 0
            for item in ex:
                ct += 1
                self.assertTrue(isinstance(item, dict))
            self.assertEqual(ct, 3)
            ct = 0

    def test_filelikeobject(self):
        with open(self.filename) as fil:
            content = StringIO(initial_value=text_type(fil.read()))
        extractor = Extractor(content)
        with extractor as ex:
            ct = 0
            for item in ex:
                ct += 1
                self.assertTrue(isinstance(item, dict))
            self.assertEqual(ct, 3)
            ct = 0


class TestFileLikeObjectInLoader(TestCase):

    def setUp(self):
        self.filename = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'data.txt')

    def test_filelikeobject(self):
        with open(self.filename) as fil:
            content = StringIO(initial_value=text_type(fil.read()))
        loader = Loader(filename=content, model_class=TestModel)
        loader.load()
        self.assertEqual(TestModel.objects.all().count(), 3)