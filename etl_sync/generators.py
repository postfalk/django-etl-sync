from __future__ import print_function
from six import text_type, binary_type
from builtins import str as text
from future.utils import iteritems

from collections import OrderedDict
from hashlib import md5
from django.core.exceptions import ValidationError, FieldError
from django.db.models import (Q, FieldDoesNotExist)
from django.forms import DateTimeField


def get_unique_fields(model_class):
    """
    Return model fields with unique=True.
    """
    return [
        f.name for f in model_class._meta.fields
        if f.unique and not f.name == 'id']


def get_internal_type(field):
    """Wrapper for Django 1.8.16 compatibility. Handles fields
    without a .get_internal_type attribute, which don't need to
    return an internal field."""
    try:
        return field.get_internal_type()
    except AttributeError:
        return None


def get_fields(model_class):
    """Wrapper for Django 1.7 compatibility. Compatibility is
    limited for performance reasons."""
    try:
        return model_class._meta.get_fields()
    except AttributeError:
        ret = []
        for fn in model_class._meta.get_all_field_names():
            try:
                ret.append(model_class._meta.get_field(fn))
            except FieldDoesNotExist:
                pass
        return ret


def get_unambiguous_fields(model_class):
    """
    Returns unambiguous field or field combination from a Django Model
    class. Will be used as a persistence criterion.
    """
    unique_together = model_class._meta.unique_together
    if unique_together:
        return list(unique_together[0])
    fields = get_fields(model_class)
    # TODO: generalize in order to handle records with id field properly
    unique_fields = [
        field.name for field in fields if getattr(field, 'unique', None) and
        field.name != 'id']
    if len(unique_fields) == 0:
        return []
    if len(unique_fields) == 1:
        return unique_fields
    raise ValidationError(
        'Failure to identify unambiguous field for {}'.format(model_class))


def get_unique_string_fields(model_class):
    """Unique string fields are used to auto normalize ForeignKey
    relations."""
    return [
        field for field in get_fields(model_class)
        if get_internal_type(field) == 'CharField' and
        field.unique]


class BaseGenerator(object):
    persistence = None

    def __init__(self, model_class, **options):
        self.model_class = model_class
        self.related_instances = {}
        self.create = options.get('create', True)
        self.update = options.get('update', True)
        self.res = None
        self.persistence = (
            self.persistence or options.get('persistence') or
            get_unambiguous_fields(self.model_class))
        if isinstance(self.persistence, (text_type, binary_type)):
            self.persistence = [self.persistence]
        self.model_fields = get_fields(self.model_class)
        self.field_names = OrderedDict([
            (field.name, get_internal_type(field))
            for field in self.model_fields])
        self.unique_string_fields = get_unique_string_fields(self.model_class)

    def get_persistence_query(self, dic, persistence, update):
        return dic, self.get_from_db(dic, persistence), update

    def get_from_db(self, dic, lookup):
        if lookup:
            query = Q()
            for fieldname in lookup:
                value = dic.get(fieldname, None)
                if value:
                    query = query & Q(**{fieldname: value})
            try:
                return self.model_class.objects.filter(query)
            except FieldError:
                pass
        return self.model_class.objects.none()

    def create_in_db(self, dic):
        return self.model_class.objects.create(**dic)

    def update_in_db(self, dic, qs):
        qs.update(**dic)
        # This save is issued to trigger signals. Not very elegant.
        qs[0].save()
        return qs[0]

    def instance_from_dic(self, dic):
        dic = self.prepare(dic)
        persistence = dic.pop('etl_persistence', self.persistence)
        create = dic.pop('etl_create', self.create)
        update = dic.pop('etl_update', self.update)
        dic, qs, update = self.get_persistence_query(dic, persistence, update)
        dic = {item:dic[item] for item in dic if item in self.field_names}
        count = len(qs)
        if count == 0 and create:
            instance = self.create_in_db(dic)
            self.res = 'created'
            return instance
        if count == 1:
            if update:
                instance = self.update_in_db(dic, qs)
                self.res = 'updated'
                return instance
            else:
                self.res = 'exists'
        if count > 1:
            raise ValidationError(
                'Double Entry found for {}'.format(persistence))

    def instance_from_int(self, pk):
        return self.model_class.objects.get(pk=pk)

    def instance_from_str(self, string):
       if len(self.unique_string_fields) == 1:
            dic = {self.unique_string_fields[0].name: string}
            return self.instance_from_dic(dic)

    def assign_related(self, instance):
        for (key, lst) in iteritems(self.related_instances):
            field = getattr(instance, key)
            try:
                field.add(*lst)
            except AttributeError:
                generator = InstanceGenerator(field.through)
                for item in lst:
                    instance = generator.get_instance({
                        field.source_field_name: instance.pk,
                        field.target_field_name: item.pk,
                        'etl_persistence': [
                            field.source_field_name,
                            field.target_field_name
                        ]})

    def get_instance(self, obj):
        """Creates, updates, and returns an instance from a dictionary."""
        if isinstance(obj, dict):
            instance = self.instance_from_dic(obj)
            self.assign_related(instance)
            return instance
        if isinstance(obj, self.model_class):
            self.res = 'exists'
            return obj
        if isinstance(obj, int):
            self.res = 'exists'
            return self.instance_from_int(obj)
        if isinstance(obj, (text_type, binary_type)):
            return self.instance_from_str(obj)

    def prepare(self, dic):
        return dic


class InstanceGenerator(BaseGenerator):
    preparations = {
        'ForeignKey': 'prepare_fk',
        'OneToOneField': 'prepare_fk',
        'ManyToManyField': 'prepare_m2m',
        'DateTimeField': 'prepare_date',
        'GeometryField': 'prepare_geometry',
        'CharField': 'prepare_text',
        'TextField': 'prepare_text',
        'BooleanField': 'prepare_boolean',
        'IntegerField': 'prepare_integer',
        'BigIntegerField': 'prepare_integer',
        'FloatField': 'prepare_float'}

    def prepare_field(self, field, value):
        return value

    def prepare_fk(self, field, value):
        return InstanceGenerator(field.rel.to).get_instance(value)

    def prepare_m2m(self, field, lst):
        # defer assignment of related instances until instance
        # creation is finished
        self.related_instances[field.name] = []
        if not isinstance(lst, list):
            lst = [lst]
        for item in lst:
            generator = InstanceGenerator(field.rel.to)
            instance = generator.get_instance(item)
            self.related_instances[field.name].append(instance)

    def prepare_date(self, field, value):
        if not (field.auto_now or field.auto_now_add):
            formfield = DateTimeField(required=not field.null)
            return formfield.clean(value)

    def prepare_text(self, field, value):
        if not isinstance(value, text_type):
            ret = text(value)
        else:
            ret = value
        if hasattr(field, 'max_length'):
            ret = ret[0:field.max_length]
        return ret

    def prepare_boolean(self, field, value):
        if value:
            return value in [1, '1', 'True', 'true', 't']
        return False

    def prepare_integer(self, field, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

    def prepare_float(self, field, value):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

    def prepare_geometry(self, field, value):
        """
        Reduce geometry to two dimensions if models. GeometryField
        dim parameter is not set otherwise.
        """
        from django.contrib.gis.geos import WKBWriter, GEOSGeometry
        if isinstance(value, (str, text_type)):
            value = GEOSGeometry(value)
        wkb_writer = WKBWriter()
        if isinstance(value, GEOSGeometry):
            if value.hasz and field.dim == 2:
                value = GEOSGeometry(wkb_writer.write(value))
        return value

    def prepare(self, dic):
        for field in get_fields(self.model_class):
            if field.name not in dic:
                continue
            fieldtype = get_internal_type(field)
            prepare_function = getattr(
                self, self.preparations[fieldtype], self.prepare_field)
            dic[field.name] = prepare_function(field, dic[field.name])
            if fieldtype == 'ManyToManyField':
                del dic[field.name]
        return dic


class HashMixin(object):
    """Mix-in adding hashing to Generators. Replaces persistence
    criterion."""
    hashfield = 'md5'
    do_not_hash_fields = ['id', 'last_modified']

    def get_persistence_query(self, dic, persistence, update):
        dic = self.hash_dic(dic)
        items = self.get_from_db(dic, [self.hashfield])
        if len(items) > 0:
            return dic, items, False
        return dic, self.get_from_db(dic, persistence), update

    def hash(self, dic):
        text_representation = ''
        fields = sorted([
            field for field in dic
            if field not in [self.hashfield] +
            list(self.do_not_hash_fields)])
        for field in fields:
            text_representation += text(dic[field])
        return md5(text_representation.encode('utf-8')).hexdigest()

    def hash_dic(self, dic):
        dic[self.hashfield] = self.hash(dic)
        return dic
