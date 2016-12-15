# Python 3.x compatibility
from __future__ import absolute_import

from unittest import TestCase
from etl_sync.transformations import Transformer
from django import forms
from datetime import datetime


class MyForm(forms.Form):
    name = forms.CharField(max_length=10)
    date = forms.DateTimeField(required=True)


class MyTransformer(Transformer):
    forms = [MyForm]


class TestTransformer(TestCase):

    def helper(self, transformer):
        transformer.cleaned_data

    def test_init(self):
        dic = {'test': 'test'}
        transformer = Transformer(dic)
        self.assertEqual(transformer.dic, dic)
        self.assertEqual(Transformer.defaults, {})
        transformer = Transformer(dic, defaults={'name': 'fred'})
        self.assertEqual(transformer.defaults, {'name': 'fred'})

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

    def test_django_forms(self):
        transformer = MyTransformer({'name': 'fred', 'date': '2001-01-01'})
        self.assertTrue(transformer.is_valid())
        self.assertIsInstance(transformer.cleaned_data['date'], datetime)
        transformer = MyTransformer({'name': 'fred'})
        self.assertFalse(transformer.is_valid())
