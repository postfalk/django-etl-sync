from django.conf import settings
from django.core.management import call_command
from django.db.models import loading
from django.test import TestCase

from bee.django_etl_sync.tests.models import TestModel
from bee.django_etl_sync.generators import *


class TestModule(TestCase):

    def setUp(self):
        pass

    def test_test_db(self):
        dics = [
            {'record': '1', 'name': 'one'},
            {'record': '2', 'name': 'two'},
            {'record': '3', 'name': 'three'},
            {'record': '1', 'name': 'one again'},
        ]

        for dic in dics:
            generator = BaseInstanceGenerator(TestModel, dic,
                                              persistence=['record'])
            generator.get_instance()

        self.assertEqual(TestModel.objects.all().count(), 3)
