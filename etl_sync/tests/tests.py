import os
from django.conf import settings
from django.core.management import call_command
from django.db.models import loading
from django.test import TestCase
from etl_sync.tests.models import (ElNumero, HashTestModel, Nombre, Numero,
                                   Polish, TestModel, TestModelWoFk)
from etl_sync.generators import BaseInstanceGenerator, InstanceGenerator
from etl_sync.mappers import Mapper
from etl_sync.readers import unicode_dic


class TestModule(TestCase):

    def setUp(self):
        pass

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
            generator = BaseInstanceGenerator(TestModelWoFk, dic)
            generator.get_instance()
        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 6)
        self.assertEqual(res.filter(record='1')[0].name, 'one')
        res.delete()
        # test with persistence criterion
        for dic in dics:
            generator = BaseInstanceGenerator(TestModelWoFk, dic,
                                              persistence='record')
            generator.get_instance()
        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 3)
        self.assertEqual(res.filter(record='1')[0].name, 'one again')
        self.assertEqual(res.filter(record='1')[0].zahl, 'vier')
        self.assertEqual(res.filter(record='2')[0].zahl, None)
        res.delete()
        # test with double persistence criterion
        for dic in dics:
            generator = BaseInstanceGenerator(TestModelWoFk, dic,
                                              persistence=['record', 'name'])
            generator.get_instance()
        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 4)
        self.assertEqual(res.filter(record='1')[0].zahl, 'vier')
        res.delete()

    def test_full_instance_generator(self):
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins', 'trash': 'rubish'},
        ]
        generator = InstanceGenerator(TestModel, dics[0], persistence=['record'])
        generator.get_instance()

    def test_fk(self):
        ins = Nombre(name='un')
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins', 'nombre': ins,
                'numero': 'uno'},
            {'record': '2', 'name': 'two', 'zahl': 'zwei', 'nombre': 'deux',
                'numero': 'due'},
            {'record': '3', 'name': 'three', 'zahl': 'drei',
                'nombre': {'name': 'troix'}, 'numero': 'tre'},
            {'record': '1', 'name': 'one', 'zahl': 'vier', 'nombre': 1,
                'numero': 'quattro'},
            {'record': '1', 'name': 'one again', 'zahl': 'fuenf',
                'nombre': 'quatre', 'numero': 'cinque'}
        ]
        for dic in dics:
            generator = InstanceGenerator(TestModel, dic, persistence='record')
            generator.get_instance()
        res = Nombre.objects.all()
        self.assertEqual(res.count(), 4)
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 3)
        self.assertEqual(res.filter(record='1')[0].nombre.name, 'quatre')
        res.delete()

    def test_fk_rejection(self):
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins',
                'nombre': {'name': 'un', 'etl_create': False},
                'numero': 'quattre'
            },
            {'record': '2', 'name': 'two', 'zahl': 'eins',
                'numero': {'name': 'uno', 'etl_create': False}
            }
        ]
        for dic in dics:
            generator = InstanceGenerator(TestModel, dic, persistence='record')
            generator.get_instance()
            result = generator.res
        # nombre example with fk that allows None
        # numero example with fk that does not allow None
        self.assertEqual(result['rejected'], True)
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
                'nombre': 'quatre', 'numero': 'cinque'}
        ]
        for dic in dics:
            generator = InstanceGenerator(TestModel, dic, persistence='record')
            generator.get_instance()
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
                'numero': 'uno'
            },
            {'record': '2', 'name': 'one', 'related': [
                    {'record': '10', 'ilosc': 'jedynka zero',
                        'persistence': 'record'},
                    {'record': '21', 'ilosc': 'dwadziescia jeden',
                        'persistence': 'record'},
                ],
                'numero': 'tre'
            },
        ]
        for dic in dics:
            generator = InstanceGenerator(TestModel, dic, persistence='record')
            generator.get_instance()
            result = generator.res
        res = Polish.objects.all()
        self.assertEqual(res.count(), 3)
        # tests also field truncation
        self.assertEqual(res.filter(record='10')[0].ilosc, 'jedynka ze')
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 2)
        self.assertEqual(len(res.filter(record='1')[0].related.values()), 2)

    def test_logging(self):
        dics = [
            {'record': '30', 'date': '3333', 'numero': 'uno'}
        ]
        for dic in dics:
            generator = InstanceGenerator(TestModel, dic, persistence='record')
            generator.get_instance()
        self.assertEqual(generator.log, '\nincorrect date: 3333, record 30')

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
                ]
            },
            {'record': 43, 'numero': 'quattre',
                'related': [
                    {'record': '10', 'ilosc': 'jedynka zero',
                        'persistence': 'record'},
                    {'record': '21', 'ilosc': 'jeden',
                        'persistence': 'record'},
                    {'record': '19', 'ilosc': 'jeden',
                        'persistence': 'record'},
                ]
            },
            {'record': 43, 'zahl': None, 'numero': 'uno'},
            {'record': 43, 'zahl': None, 'numero': None}
        ]
        for dic in dics:
            generator = InstanceGenerator(HashTestModel, dic, persistence='record')
            generator.get_instance()
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
                    ]
                },
                {'record': 43, 'numero': 'quattre',
                    'related': [
                        {'record': '10', 'ilosc': 'jedynka zero'},
                        {'record': '21', 'ilosc': 'jeden'},
                        {'record': '19', 'ilosc': 'jeden'}
                    ]
                },
                {'record': 43, 'zahl': None, 'numero': 'uno'},
                {'record': 43, 'zahl': None, 'numero': None},
                {'record': 43, 'numero': 'tres',
                    'related': [
                        {'record': '10', 'ilosc': 'jedynka zero'},
                        {'record': '21', 'ilosc': 'dwadziescia jeden'}
                    ]
                },
            ]
        for dic in dics:
            generator = InstanceGenerator(HashTestModel, dic, persistence='record')
            generator.get_instance()
        res = Polish.objects.all()
        self.assertEqual(res.count(), 3)


class TestUpdate(TestCase):
    """
    Test decision whether to update or to ignore.
    """

    def setUp(self):
        pass

    def test_double_load(self):
        dics = [
            {'record': 111, 'numero': 'uno'}
        ]
        for dic in dics:
            generator = InstanceGenerator(HashTestModel, dic, persistence=
                'record')
            generator.get_instance()
            self.assertEqual(generator.res['created'], True)
            self.assertEqual(generator.res['updated'], False)
            self.assertEqual(generator.res['exists'], False)
            generator = InstanceGenerator(HashTestModel, dic, persistence=
                'record')
            generator.get_instance()
            self.assertEqual(generator.res['created'], False)
            self.assertEqual(generator.res['updated'], False)
            self.assertEqual(generator.res['exists'], True)
            dic['numero'] = 2
            generator = InstanceGenerator(HashTestModel, dic, persistence=
                'record')
            generator.get_instance()
            self.assertEqual(generator.res['created'], False)
            self.assertEqual(generator.res['updated'], True)
            self.assertEqual(generator.res['exists'], False)


class TestLoad(TestCase):
    """
    Tests data loading from file.
    """

    def setUp(self):
        pass

    def test_load_from_file(self):
        path = os.path.dirname(os.path.realpath(__file__))
        filename='{0}/data.txt'.format(path)
        mapper = Mapper(filename=filename, model_class=TestModel)
        mapper.load()
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 3)


class TestReaders(TestCase):
    """
    Test readers, encoding problems in particular.
    """

    def setUp(self):
        pass

    def test_dic_decoder(self):
        testdic = {'word': 'testword', 'number': 68898, 'utf8': 'testing\xc2\xa0'}
        dic = unicode_dic(testdic, 'utf-8')
        self.assertEqual(dic['utf8'], u'testing\xa0')
