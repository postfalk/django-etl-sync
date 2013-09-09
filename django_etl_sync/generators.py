# python 3 preparations
from __future__ import print_function
# python
import re
import sys
import json
import os
import warnings
import unicodecsv as csv
from datetime import datetime
from hashlib import md5
# django
from django.db.models import Q
from django.db import IntegrityError
from django.db.models.fields import FieldDoesNotExist
from django.forms.models import model_to_dict
from django.forms import DateTimeField, ValidationError

# TODO: remove all local references
# from bee import settings
# from bee.etl.functions import get_or_create_local_path
# from bee.etl.forms import model_to_modelform
# from bee.etl.generic_transformations import (lower_case_dic,
#    get_remote_recource_link_from_template, format_lowercase,
#    replace_empty_string_with_none)


class BaseInstanceGenerator(object):
    model_class = None
    dic = {}
    persistence = []
    create_foreign_key = True
    save = True
    update = True
    create = True

    def __init__(self, model_class, dic, **kwargs):
        """
        Set options from kwargs and dic params (TODO: add this part.).
        """
        self.model_class = model_class
        self.dic = dic

        for k in kwargs:
            setattr(self, k, kwargs[k])

        self.res = {'updated': False, 'created': False, 'rejected': False,
                    'exists': False}

        try:
            self.persistence = dic['persistence']
            del dic['persistence']
        except KeyError:
            pass

        try:
            self.create = dic['etl_create']
            del dic['etl_create']
        except KeyError:
            pass

        if not isinstance(self.persistence, list):
            self.persistence = [self.persistence]

        self.related_instances = {}

    def prepare(self, dic):
        """
        Basic model to dic conversion works only for models without any related
        type. Subclass for more complicated preparations.
        """
        return self.model_class(**dic)

    def get_instance(self):
        """
        Create or get instance and add relate it to the database. Try to make
        this general enough so that subclassing is not necessary.
        1. Check whether instance already saved.
        2. Check whether instance fulfilling persistence already exists.
            a) no -> save
            b) yes -> update
        """

        model_instance = self.prepare(self.dic)

        if model_instance.pk:
            self.res['exists'] = True
            return model_instance

        if hasattr(model_instance, 'md5'):
            model_instance.md5 = model_instance.get_md5()
            if self.model_class.objects.filter(md5=model_instance.md5).exists():
                self.res['exists'] = True
                return model_instance

        query = Q()
        for pd in self.persistence:
            try:
                attr = getattr(model_instance, pd)
            except AttributeError:
                pass
            else:
                if attr:
                    query = query & Q(**{'{0}'.format(pd): attr})
        result = self.model_class.objects.all().filter(query)
        record_count = result.count()

        if record_count == 0 and self.create:
            try:
                model_instance.save()
            except IntegrityError:
                self.res['rejected'] = True
                return None
            else:
                self.res['created'] = True

        elif record_count == 1:

            if self.update:
                dic = model_to_dict(model_instance)
                for d in dic.copy():
                    ft = model_instance._meta.get_field(d).get_internal_type()
                    if ft == 'ManyToManyField':
                        del dic[d]
                del dic['id']

                result.update(**dic)
                self.res['updated'] = True
            else:
                self.res['exists'] = True
            model_instance = result[0]

        else:
            self.res['rejected'] = True
            return model_instance

        for r in self.related_instances:
            getattr(model_instance, r).add(*self.related_instances[r])

        return model_instance


class InstanceGenerator(BaseInstanceGenerator):

    def prepare(self, dic):
        model_instance = self.model_class()

        for fieldname in dic:

            try:
                field = model_instance._meta.get_field(fieldname)
            except (AttributeError, FieldDoesNotExist):
                continue
            else:
                fieldtype = field.get_internal_type()

            if fieldtype == 'ForeignKey':
                fieldvalue = FkInstanceGenerator(field, dic).get_instance()

            elif fieldtype == 'ManyToManyField':
                if isinstance(dic[fieldname], list):
                    # defer assignment of related instances until instance
                    # creation is finished
                    for d in dic[fieldname]:
                        self.related_instances[fieldname] = []
                        generator = RelInstanceGenerator(field, d)
                        self.related_instances[fieldname].append(
                            generator.get_instance())

            elif fieldtype == 'DateTimeField':
                validator = DateTimeField()
                try:
                    cleaned_field = validator.clean(self.dic[fieldname])
                except ValidationError:
                    print('incorrect {0}: {1}, line {2}'.format(
                        fieldname, dic[fieldname], dic['record']))
                        #, file=self.logfile)
                    fieldvalue = None
                else:
                    fieldvalue = cleaned_field

            elif fieldtype == 'GeometryField':
                fieldvalue = dic[fieldname]

            else:
                fieldvalue = dic[fieldname]
                try:
                    fieldvalue = fieldvalue[0:field.max_length]
                except TypeError:
                    pass

            try:
                setattr(model_instance, fieldname, fieldvalue)
            except ValueError:
                pass

        return model_instance


class RelInstanceGenerator(InstanceGenerator):
    """
    This class prepares related records in M2M relationships.
    """

    def __init__(self, field, dic, **kwargs):
        super(RelInstanceGenerator, self).__init__(None, dic, **kwargs)
        self.model_class = field.rel.to


class FkInstanceGenerator(RelInstanceGenerator):
    """
    This class makes special preparations for saving ForeignKey records while
    preparing records for saving.
    """

    def __init__(self, field, dic, **kwargs):
        super(FkInstanceGenerator, self).__init__(field, dic, **kwargs)
        self.field = field
        self.related_field = field.rel.field_name
        self.update = False

    def prepare(self, dic):

        RelField = self.related_field
        fieldname = self.field.name
        value = dic[fieldname]
        fk_dic = dic.copy()
        instance = None

        model_instance = self.model_class()

        if isinstance(value, self.model_class):
            ret = value
        else:
            if isinstance(value, dict):
                fk_dic = value
                if 'name' in fk_dic and RelField == 'id':
                    self.persistence = ['name']
                else:
                    pers = [RelField]
            elif isinstance(value, int):
                fk_dic = {RelField: value}
                self.persistence = [RelField]
            else:
                if RelField == 'id':
                    fk_dic['name'] = fk_dic[fieldname]
                    self.persistence = ['name']
                else:
                    fk_dic = {RelField: value}
                    self.persistence = [RelField]

            ret = super(FkInstanceGenerator, self).prepare(fk_dic)
        return ret

