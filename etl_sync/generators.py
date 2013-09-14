# python 3 preparations
from __future__ import print_function
# python
import sys
import os
import warnings
import unicodecsv as csv
from datetime import datetime
from hashlib import md5
# django
from django.db.models import Q
from django.db import IntegrityError, DatabaseError
from django.db.models.fields import FieldDoesNotExist
from django.forms.models import model_to_dict
from django.forms import DateTimeField, ValidationError


def indent_log(message):
    if message:
        message = '  ' + message.replace('\n', '\n  ')
    return message


def append_log(log, message):
    if message:
        log = '{0}\n{1}'.format(log, message)
    return log


def get_unique_fields(Model):
    ret = []
    for f in Model._meta.fields:
        if f.unique:
            ret.append(f.name)
    return ret


class BaseInstanceGenerator(object):
    model_class = None
    dic = {}
    persistence = None
    create_foreign_key = True
    save = True
    update = True
    create = True
    log = ''

    # rename dic because it is not necessarily a dic
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

        if isinstance(dic, dict):
            if 'persistence' in dic:
                self.persistence = dic['persistence']
                del dic['persistence']

            if 'etl_create' in dic:
                self.create = dic['etl_create']
                del dic['etl_create']

        if self.persistence and not isinstance(self.persistence, list):
            self.persistence = [self.persistence]

        self.related_instances = {}

    def prepare(self, dic):
        """
        Basic model to dic conversion works only for models without any related
        type. Subclass for more complicated preparations.
        """
        return self.model_class(**dic)

    def hash_instance(self, instance):
        """
        Method for hashing.
        """
        fields = instance._meta.fields
        out = u''
        for f in fields:
            if not f.name in [u'md5', u'id']:
                try:
                    value = unicode(getattr(instance, f.name))
                except TypeError:
                    pass
                else:
                    if value:
                        out = out + value
        ret = md5(out.encode('utf-8')).hexdigest()
        return ret

    def get_persistence_query(self, model_instance, persistence):
        query = Q()
        for pd in persistence:
                try:
                    attr = getattr(model_instance, pd)
                except AttributeError:
                    pass
                else:
                    if attr:
                        query = query & Q(**{'{0}'.format(pd): attr})
        return model_instance.__class__.objects.filter(query)

    def get_instance(self):
        """
        Create or get instance and add relate it to the database. Try to make
        this general enough so that subclassing is not necessary.
        1. Check whether instance already saved.
        2. Check whether instance with persistence already exists.
            a) no -> save
            b) yes -> update
        """

        model_instance = self.prepare(self.dic)
        # if hasattr(model_instance, 'record'):
        #    print(model_instance.record)

        if model_instance.pk:
            self.res['exists'] = True
            return model_instance

        if hasattr(model_instance, 'md5'):
            hashvalue = self.hash_instance(model_instance)
            model_instance.md5 = hashvalue
            res = self.model_class.objects.filter(md5=hashvalue)
            if res.count() != 0:
                self.res['exists'] = True
                return res[0]

        if self.persistence:
            result = self.get_persistence_query(model_instance, self.persistence)
            record_count = result.count()
        else:
            uf = get_unique_fields(model_instance)
            if 'id' in uf:
                uf.remove('id')
            if len(uf) > 0:
                result = self.get_persistence_query(model_instance, uf)
                record_count = result.count()
            else:
                record_count = 0

        if record_count == 0 and self.create:
            try:
                model_instance.save()
            except (IntegrityError, DatabaseError, ValidationError):
                self.res['rejected'] = True
            else:
                self.res['created'] = True

        elif record_count == 1:

            if self.update:
                dic = model_to_dict(model_instance)
                del dic['id']
                for d in dic.copy():
                    ft = model_instance._meta.get_field(d).get_internal_type()
                    if ft == 'ManyToManyField' or not d in self.dic:
                        del dic[d]
                try:
                    result.update(**dic)
                except (IntegrityError, DatabaseError):
                    self.res['rejected'] = True
                    return model_instance
                else:
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
                fieldvalue = FkInstanceGenerator(field, dic[fieldname]
                    ).get_instance()

            elif fieldtype == 'ManyToManyField':
                if isinstance(dic[fieldname], list):
                    # defer assignment of related instances until instance
                    # creation is finished
                    self.related_instances[fieldname] = []
                    for d in dic[fieldname]:
                        generator = RelInstanceGenerator(field, d)
                        self.related_instances[fieldname].append(
                            generator.get_instance())

            elif fieldtype == 'DateTimeField':
                validator = DateTimeField()
                try:
                    cleaned_field = validator.clean(self.dic[fieldname])
                except ValidationError:
                    message = 'incorrect {0}: {1}, record {2}'.format(
                        fieldname, dic[fieldname], dic['record'])
                    self.log = append_log(self.log, message)
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

    def prepare(self, value):

        RelField = self.related_field
        fieldname = self.field.name
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
                    fk_dic = {'name': value}
                    self.persistence = ['name']
                else:
                    fk_dic = {RelField: value}
                    self.persistence = [RelField]

            ret = super(FkInstanceGenerator, self).prepare(fk_dic)
        return ret

