"""
Classes that generate model instances from dictionaries.
"""
# python 3 preparations
from __future__ import print_function
# python
from hashlib import md5
import os
# django
from django.db.models import Q
from django.db import IntegrityError, DatabaseError
from django.db.models.fields import FieldDoesNotExist
from django.forms.models import model_to_dict
from django.forms import DateTimeField, ValidationError


def indent_log(message):
    """
    Indenting log messages from subroutines.
    """
    if message:
        message = '  ' + message.replace('\n', '\n  ')
    return message


def append_log(log, message):
    """
    Appending messages to log.
    """
    if message:
        log = '{0}\n{1}'.format(log, message)
    return log


def get_unique_fields(model_class):
    """
    Get model fields with attribute unique.
    """
    ret = []
    for field in model_class._meta.fields:
        if field.unique:
            ret.append(field.name)
    return ret


def hash_instance(instance):
    """
    Method for hashing.
    """
    fields = instance._meta.fields
    out = u''
    for field in fields:
        if not field.name in [u'md5', u'id']:
            try:
                value = unicode(getattr(instance, field.name))
            except TypeError:
                pass
            else:
                if value:
                    out = out + value
    ret = md5(out.encode('utf-8')).hexdigest()
    return ret


class BaseInstanceGenerator(object):
    """
    Generates, evaluates, and saves instances from dictionary.
    """

    def __init__(self, model_class, dic,
                 persistence=None,
                 create_foreign_key=True,
                 save=True,
                 update=True,
                 create=True):
        """
        Set options from kwargs and dic params (TODO: add this part.).
        """
        self.model_class = model_class
        self.dic = dic or {}
        self.persistence = persistence
        self.create_foreign_key = create_foreign_key
        self.save = save
        self.update = update
        self.create = create
        self.log = ''
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
        Basic model to dic conversion works only for models without relational
        field type. Subclass for more complicated preparations.
        """
        return self.model_class(**dic)

    def get_persistence_query(self, model_instance, persistence):
        """
        Get the query to determine whether record already exists
        depending on persistence definition.
        """
        query = Q()
        for pfield in persistence:
            try:
                attr = getattr(model_instance, pfield)
            except AttributeError:
                pass
            else:
                if attr:
                    query = query & Q(**{pfield: attr})
        return self.model_class.objects.filter(query)

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
        if not model_instance:
            self.res['rejected'] = True
            return None

        if model_instance.pk:
            self.res['exists'] = True
            return model_instance

        if hasattr(model_instance, 'md5'):
            hashvalue = hash_instance(model_instance)
            model_instance.md5 = hashvalue
            res = self.model_class.objects.filter(md5=hashvalue)
            if res.count() != 0:
                self.res['exists'] = True
                return res[0]

        if self.persistence:
            result = self.get_persistence_query(model_instance,
                                                self.persistence)
            record_count = result.count()
        else:
            unique_fields = get_unique_fields(model_instance)
            if 'id' in unique_fields:
                unique_fields.remove('id')
            if len(unique_fields) > 0:
                result = self.get_persistence_query(model_instance,
                    unique_fields)
                record_count = result.count()
            else:
                record_count = 0

        if record_count == 0 and self.create:
            try:
                model_instance.clean_fields()
            except ValidationError as error:
                print(model_instance.__class__, model_to_dict(model_instance))
                print(error.message_dict)
                self.res['rejected'] = True
            else:
                try:
                    model_instance.save()
                except IntegrityError:
                    self.res['rejected'] = True
                else:
                    self.res['created'] = True

        elif record_count == 1:

            if self.update:
                dic = model_to_dict(model_instance)
                del dic['id']
                for key in dic.copy():
                    field_type = model_instance._meta.get_field(key
                        ).get_internal_type()
                    if field_type == 'ManyToManyField' or not key in self.dic:
                        del dic[key]
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

        for key in self.related_instances:
            try:
                getattr(model_instance, key).add(*self.related_instances[key])
            except ValueError:
                pass

        return model_instance


class InstanceGenerator(BaseInstanceGenerator):
    """
    Instance generator that can take of foreign key and many-to-many-
    relationships.
    """
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
                    for entry in dic[fieldname]:
                        generator = RelInstanceGenerator(field, entry)
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

            elif fieldtype == 'CharField' or fieldtype == 'TextField':
                if not dic[fieldname]:
                    fieldvalue = ''
                if hasattr(field, 'max_length'):
                    fieldvalue = unicode(dic[fieldname])
                    fieldvalue = fieldvalue[0:field.max_length]
                else:
                    fieldvalue = dic[fieldname]

            else:
                fieldvalue = dic[fieldname]

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
        if not value:
            return None

        related_field_class = self.related_field

        if isinstance(value, self.model_class):
            ret = value
        else:
            if isinstance(value, dict):
                fk_dic = value
                if 'name' in fk_dic and related_field_class == 'id':
                    self.persistence = ['name']
            elif isinstance(value, int):
                fk_dic = {related_field_class: value}
                self.persistence = [related_field_class]
            else:
                if related_field_class == 'id':
                    fk_dic = {'name': value}
                    self.persistence = ['name']
                else:
                    fk_dic = {related_field_class: value}
                    self.persistence = [related_field_class]

            ret = super(FkInstanceGenerator, self).prepare(fk_dic)
        return ret
