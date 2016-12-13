from __future__ import print_function
from six import text_type, binary_type
from builtins import str as text
from future.utils import iteritems
from hashlib import md5
from django.utils import version
from django.core.exceptions import ValidationError
from django.db.models import Q, Model, FieldDoesNotExist
from django.forms.models import model_to_dict
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
            except model_class.FieldDoesNotExist:
                pass
        return ret


def get_unambiguous_fields(model_class):
    """
    Returns unambiguous field or field combination from a Django Model
    class. Will be used as a persistence criterion.
    """
    unique_together = model_class._meta.unique_together
    if unique_together:
        return unique_together[0]
    fields = get_fields(model_class)
    unique_fields = [
        field.name for field in fields if getattr(field, 'unique', None)]
    if len(unique_fields) == 0:
        return []
    if len(unique_fields) == 1:
        return unique_fields
    raise ValidationError(
        'Failure to identify unambiguous field for {}'.format(model_class))


class BaseGenerator(object):

    def __init__(self, model_class, **options):
        self.model_class = model_class
        self.persistence = options.get('persistence', [])
        self.related_instances = {}
        self.create = options.get('create', True)
        self.update = options.get('update', True)

    def get_persistence_query(self, dic, persistence):
        print('HERE', dic)
        query = Q()
        for fieldname in persistence:
            value = getattr(self.model_class, fieldname, None)
            if value:
                query = query & Q(**{fieldname: value})
        return self.model_class.objects.filter(query)

    def create_in_db(self, dic):
        return self.model_class.objects.create(**dic)

    def update_in_db(self, dic, qs):
        qs.update(**dic)
        return qs[0]

    def get_instance(self, dic):
        """Creates, updates, and returns an instance from a dictionary."""
        model_instance = self.prepare(dic)
        persistence = self.persistence or get_unambiguous_fields(
            self.model_class)
        if isinstance(dic, dict):
            persistence = dic.pop('etl_persistence', persistence)
            create = dic.pop('etl_create', self.create)
            update = dic.pop('etl_update', self.update)
        qs = self.get_persistence_query(dic, persistence)
        count = len(qs)
        if count == 0:
            instance = self.create_in_db(dic)
        if count == 1:
            instance = self.update_in_db(dic, qs)
        if count > 1:
            raise ValidationError(
                'Double Entry found for {}'.format(persistence))
        return instance

    def prepare(self, dic):
        """Final transformations depending on the field type."""
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

    def prepare_m2m(self, field, value):
        # defer assignment of related instances until instance
        # creation is finished
        if not isinstance(value, list):
            value = [value]
        self.related_instances[field.name] = []
        for entry in value:
            generator = RelInstanceGenerator(field)
            instance = generator.get_instance(entry)
            self.related_instances[field.name].append(instance)

    def prepare_date(self, field, value):
        if not (field.auto_now or field.auto_now_add):
            formfield = DateTimeField(required=not field.null)
            return formfield.clean(value)

    def prepare_text(self, field, value):
        if not isinstance(value, (text_type, binary_type)):
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
        return dic


class RelatedInstanceGenerator(InstanceGenerator):
    pass


class FKInstanceGenerator(InstanceGenerator):
    pass

