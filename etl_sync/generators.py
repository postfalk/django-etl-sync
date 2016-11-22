"""
Generate model instances from dictionaries.
"""

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


VERSION = version.get_version()[2]


def get_internal_type(field):
    """This is a wrapper for compatibility with Django 1.8.16. It works
    with fields that don't have a .get_internal_type attribute"""
    try:
        return field.get_internal_type()
    except AttributeError:
        return None


def set_model_attribute(instance, field, value):
    """This is a wrapper for backwards compatibility with Django 1.7."""
    if get_internal_type(field) in ['ManyToManyField']:
        pass
    else:
        setattr(instance, field.name, value)


def get_fields(model_class):
    """This is a wrapper for backwards compatibility with Django 1.7.
    It is currently not fully compatible for performance reasons."""
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


def get_unique_fields(model_class):
    """
    Return model fields with unique=True.
    """
    return [
        f.name for f in model_class._meta.fields
        if f.unique and not f.name == 'id']


def get_unambiguous_fields(model_class):
    """
    Returns unambiguous field from Fk model. Defaults to name.
    This will be only successful if there is ONLY one single CharField
    or only one unique CharField. All other cases must be specified in
    more detail.
    """
    unique_together = model_class._meta.unique_together
    if len(unique_together) == 1:
        return list(unique_together[0])
    fields = get_fields(model_class)
    char_fields = [f for f in fields if get_internal_type(f) == 'CharField']
    name_field = [f.name for f in char_fields if f.name == 'name']
    if name_field:
        return name_field
    if len(char_fields) == 1:
        return [f.name for f in char_fields]
    unique_char_fields = [f.name for f in char_fields if getattr(f, 'unique', None)]
    if len(unique_char_fields) == 1:
        return unique_char_fields
    raise ValidationError(
        'Failure to identify unambiguous field for {}'.format(model_class))


class BaseInstanceGenerator(object):
    """
    Generates, evaluates, and saves model instances from dictionary
    or object.
    """
    hashfield = 'md5'
    do_not_hash_fields = ['id', 'last_modified']

    def __init__(self, model_class, dic, **kwargs):
        """
        Set options from kwargs and dictionary items.
        """
        self.model_class = model_class
        self.dic = dic or {}
        self.persistence = kwargs.pop('persistence', [])
        self.create_foreign_key = kwargs.pop(
            'create_foreign_key', True)
        self.save = kwargs.pop('save', True)
        self.update = kwargs.pop('update', True)
        self.create = kwargs.pop('create', True)
        self.res = {'updated': False, 'created': False, 'exists': False}
        # overwrite defaults by values in nested dictionary
        # otherwise inherit from parents
        if isinstance(dic, dict):
            self.persistence = dic.pop('etl_persistence', self.persistence)
            self.create = dic.pop('etl_create', self.create)
        if not isinstance(self.persistence, list):
            self.persistence = [self.persistence]
        self.related_instances = {}

    def hash_instance(self, instance):
        # TODO: recreate as pure function
        """Hash extracted dictionary. Override if you like.

        Args:
            instance (models.Model):

        Returns:
            md5.hexdigest

        """
        out = u''
        for field in instance._meta.fields:
            if field.name not in [self.hashfield] + self.do_not_hash_fields:
                value = getattr(instance, field.name, '')
                if isinstance(value, Model):
                    value = value.pk
                out += text(value)
        return md5(out.encode('utf-8')).hexdigest()

    def _check_hash(self, instance, fieldname):
        """Returns the number of instances that match the hash of
        a given new instance. Also returns the query for update operations.

        Args:
            instance (models.Model): New instance to hash
            fieldname (str): name of the field where hash will be stored

        Returns:
            Tuple: Number of finds, queryset to retrieve records matching hash

        """
        qs = self.model_class.objects.none()
        if hasattr(instance, fieldname):
            value = self.hash_instance(instance)
            setattr(instance, fieldname, value)
            qs = self.model_class.objects.filter(**{fieldname: value})
        return qs.count(), qs

    def _get_persistence_query(self, model_instance, persistence):
        """
        Returns query to determine whether record already exists
        depending on persistence criteria.
        """
        # TODO: pure function?
        query = Q()
        for fieldname in persistence:
            value = getattr(model_instance, fieldname, None)
            if value:
                query = query & Q(**{fieldname: value})
        return self.model_class.objects.filter(query)

    def _check_persistence(self, instance, persistence):
        # TODO: pure function?
        """
        Returns the number of records fulfilling the
        persistence criterion and the query set resulting from
        the application of the persistence criterion.
        """
        if not persistence:
            unique_fields = get_unique_fields(instance)
            if not unique_fields:
                return 0, None
            persistence = unique_fields
        qs = self._get_persistence_query(instance, persistence)
        return qs.count(), qs

    def _assign_related(self, instance, rel_inst_dic, dic={}):
        # TODO: pure function?
        """
        Assign related instances after saving the parent
        record. The instances should be fully prepared and
        clean at this point. Use the original dic to fill
        in intermediate relationships.
        """
        for (key, lst) in iteritems(rel_inst_dic):
            field = getattr(instance, key)
            try:
                field.add(*lst)
            except AttributeError:
                # Deal with M2M fields with through model here.
                # Explicitly generate connecting relationship
                for i, item in enumerate(lst):
                    newdic = dic[key][i].copy()
                    newdic.update({
                        field.source_field_name: instance,
                        field.target_field_name: item})
                    generator = InstanceGenerator(
                        field.through, newdic, persistence=[
                            field.source_field_name, field.target_field_name],
                        create_foreign_key=False)
                    generator.get_instance()

    def create_in_db(self, instance, persistence_qs):
        """
        Creates new entry in database.
        """
        if self.create:
            instance.clean_fields()
            instance.save()
            self.res['created'] = True
            return instance

    def update_in_db(self, instance, persistence_qs):
        """
        Update in database.
        """
        if self.update:
            dic = model_to_dict(instance)
            for key in dic.copy():
                field_type = instance._meta.get_field(
                    key).get_internal_type()
                if (
                    field_type == 'ManyToManyField' or
                    key not in self.dic and
                    key != self.hashfield
                ):
                    del dic[key]
            # see whether that suits us here, check whether M2M field
            # updates work as well (as they should since they are treated
            # separately)
            persistence_qs.update(**dic)
            # add this here to make sure post_save signals are broadcast
            persistence_qs[0].save()
            self.res['updated'] = True
        self.res['exists'] = True
        return persistence_qs[0]

    def prepare(self, dic):
        """
        Basic dictionary to model conversion. Works only for models
        without relational fields. Override this method for
        more complicated preparations.
        """
        return self.model_class(**dic)

    def get_instance(self):
        """
        Creates and/or returns instance, adds it to the database, and creates
        relationships.
        """
        model_instance = self.prepare(self.dic)
        self.res = {'updated': False, 'created': False, 'exists': False}
        if model_instance:
            if model_instance.pk:
                self.res['exists'] = True
                return model_instance
            count, qs = self._check_hash(
                model_instance, self.hashfield)
            if count != 0:
                self.res['exists'] = True
                return qs[0]
            count, qs = self._check_persistence(
                model_instance, self.persistence)
            try:
                model_instance = [
                    self.create_in_db, self.update_in_db][count](
                        model_instance, qs)
            except IndexError:
                # TODO: Arriving in this branch means that more than one
                # record fulfills the persistence criterion.
                # Add error handling.
                string = ''
                for key in self.persistence:
                    string += ', ' + key
                print('Double entry found for {}'.format(string))
                return model_instance
            self._assign_related(
                model_instance, self.related_instances, self.dic)
            return model_instance


class InstanceGenerator(BaseInstanceGenerator):
    """
    Instance generator, handles related fields.
    """

    def _prepare_field(self, field, value):
        return value

    def _prepare_fk(self, field, value):
        return FkInstanceGenerator(field, value).get_instance()

    def _prepare_m2m(self, field, value):
        # defer assignment of related instances until instance
        # creation is finished
        if not isinstance(value, list):
            value = [value]
        self.related_instances[field.name] = []
        for entry in value:
            generator = RelInstanceGenerator(field, entry)
            instance = generator.get_instance()
            self.related_instances[field.name].append(instance)

    def _prepare_date(self, field, value):
        if not (field.auto_now or field.auto_now_add):
            formfield = DateTimeField(required=not field.null)
            return formfield.clean(value)

    def _prepare_text(self, field, value):
        if not isinstance(value, (text_type, binary_type)):
            ret = text(value)
        else:
            ret = value
        if hasattr(field, 'max_length'):
            ret = ret[0:field.max_length]
        return ret

    def _prepare_boolean(self, field, value):
        if value:
            return value in [1, '1', 'True', 'true', 't']
        return False

    def _prepare_integer(self, field, value):
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

    def _prepare_float(self, field, value):
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

    def _prepare_geometry(self, field, value):
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

    preparations = {
        'ForeignKey': _prepare_fk,
        'OneToOneField': _prepare_fk,
        'ManyToManyField': _prepare_m2m,
        'DateTimeField': _prepare_date,
        'GeometryField': _prepare_geometry,
        'CharField': _prepare_text,
        'TextField': _prepare_text,
        'BooleanField': _prepare_boolean,
        'IntegerField': _prepare_integer,
        'BigIntegerField': _prepare_integer,
        'FloatField': _prepare_float
    }

    def prepare(self, dic):
        if isinstance(dic, self.model_class):
            return dic
        model_instance = self.model_class()
        for field in get_fields(model_instance):
            if field.name not in dic:
                continue
            fieldtype = get_internal_type(field)
            try:
                value = self.preparations[fieldtype](
                    self, field, dic[field.name])
            except KeyError:
                value = dic[field.name]
            try:
                set_model_attribute(model_instance, field, value)
            except (AttributeError, ValueError, TypeError):
                pass
        return model_instance


class RelInstanceGenerator(InstanceGenerator):
    """
    Prepares related instances in M2M relationships.
    """

    def __init__(self, field, dic, **kwargs):
        super(RelInstanceGenerator, self).__init__(None, dic, **kwargs)
        self.model_class = field.rel.to


class FkInstanceGenerator(RelInstanceGenerator):
    """
    Prepares ForeignKey instances.

    Order of assignment attempts: 1. Instance,
    2. Dictionary, 3. Integer, 4. Unique name or single field.
    """

    def __init__(self, field, dic, **kwargs):
        super(FkInstanceGenerator, self).__init__(field, dic, **kwargs)
        self.field = field
        self.related_field = field.rel.field_name
        try:
            self.update = dic.pop('etl_update', False)
        except AttributeError:
            self.update = False

    def prepare_instance(self, value):
        return value

    def prepare_dict(self, value):
        if self.persistence:
            return super(FkInstanceGenerator, self).prepare(value)
        keys = get_unambiguous_fields(self.model_class)
        if all(key in value for key in keys) and self.related_field == 'id':
            self.persistence = keys
            return super(FkInstanceGenerator, self).prepare(value)
        else:
            raise ValidationError(
                'Related object cannot be determined for {}'
                ''.format(self.model_class))

    def prepare_int(self, value):
        fk_dic = {self.related_field: value}
        self.persistence = [self.related_field]
        return super(FkInstanceGenerator, self).prepare(fk_dic)

    def prepare_others(self, value):
        keys = get_unambiguous_fields(self.model_class)
        if len(keys) == 1:
            key = keys[0]
            if self.related_field == 'id':
                fk_dic = {key: value}
                self.persistence = [key]
            else:
                fk_dic = {self.related_field: value}
                self.persistence = [self.related_field]
            return super(FkInstanceGenerator, self).prepare(fk_dic)
        else:
            raise ValidationError(
                 'Failure to identify unambiguous fields for {}'
                 ''.format(self.model_class))

    def prepare(self, value):
        if value:
            if isinstance(value, self.model_class):
                return self.prepare_instance(value)
            if isinstance(value, dict):
                return self.prepare_dict(value)
            if isinstance(value, int):
                return self.prepare_int(value)
            return self.prepare_others(value)
