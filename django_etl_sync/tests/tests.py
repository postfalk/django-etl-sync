from django.conf import settings
from django.core.management import call_command
from django.db.models import loading
from django.test import TestCase

from django_etl_sync.tests.models import *
from django_etl_sync.generators import *
from django_etl_sync.mappers import Mapper


class TestModule(TestCase):

    def setUp(self):
        pass

    def test_test_db(self):
        dics = [
            {'record': '1', 'name': 'one', 'zahl': 'eins'},
            {'record': '2', 'name': 'two', 'zahl': 'zwei'},
            {'record': '3', 'name': 'three', 'zahl': 'drei'},
            {'record': '1', 'name': 'one', 'zahl': 'vier'},
            {'record': '1', 'name': 'one again', 'zahl': 'fuenf'}
        ]

        # test without persistence criterion
        for dic in dics:
            generator = BaseInstanceGenerator(TestModelWoFk, dic)
            generator.get_instance()

        res = TestModelWoFk.objects.all()
        self.assertEqual(res.count(), 5)
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
                'numero': ''
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
        # numero example with fk that allows not None
        self.assertEqual(result['rejected'], True)
        self.assertEqual(result['created'], False)
        self.assertEqual(result['updated'], False)
        self.assertEqual(Nombre.objects.all().count(), 0)
        res = TestModel.objects.all()
        self.assertEqual(res.count(), 1)
        self.assertEqual(res[0].nombre, None)

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


class TestLoad(TestCase):
    """
    Tests data loading from file.
    """

    def setUp(self):
        pass

    def test_load_from_file(self):
        #path = os.path.dirname(os.path.realpath(__file__))
        #dic = {'filename': '{0}/data.csv'.format(path), 'name': 'test',
        #       'model_class': TestModel, 'persistence': 'record'}
        #mapper = Mapper(dic)
        #mapper.load()
        #res = TestModel.objects.all()
        #self.assertEqual(res.count(), 3)
