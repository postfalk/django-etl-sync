"""Classes that generate model instances from dictionaries."""
from __future__ import print_function
from hashlib import md5
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms.models import model_to_dict
from django.forms import DateTimeField


def get_unique_fields(model_class):
    """Get model fields with attribute unique."""
    ret = []
    for field in model_class._meta.fields:
        if field.unique and not field.name == 'id':
            ret.append(field.name)
    return ret


class BaseInstanceGenerator(object):
    """Generates, evaluates, and saves instances from dictionary
    or object."""
    hashfield = 'md5'

    def __init__(self, model_class, dic, persistence=None,
                 create_foreign_key=True, save=True, update=True,
                 create=True):
        """Set options from kwargs and dic params."""
        self.model_class = model_class
        self.dic = dic or {}
        self.persistence = persistence
        self.create_foreign_key = create_foreign_key
        self.save = save
        self.update = update
        self.create = create
        self.res = {'updated': False, 'created': False, 'exists': False}
        if isinstance(dic, dict):
            if 'etl_persistence' in dic:
                self.persistence = dic['etl_persistence']
                del dic['etl_persistence']
            if 'etl_create' in dic:
                self.create = dic['etl_create']
                del dic['etl_create']
        if self.persistence and not isinstance(self.persistence, list):
            self.persistence = [self.persistence]
        self.related_instances = {}

    def hash_instance(self, instance):
        """Method for hashing."""
        fields = instance._meta.fields
        out = u''
        for field in fields:
            if field.name not in [self.hashfield, u'id', u'last_modified']:
                try:
                    value = unicode(getattr(instance, field.name))
                except TypeError:
                    pass
                else:
                    if value:
                        out = out + value
        ret = md5(out.encode('utf-8')).hexdigest()
        return ret

    def _get_persistence_query(self, model_instance, persistence):
        """Get query to determine whether record already exists
        depending on persistence definition."""
        query = Q()
        for fieldname in persistence:
            try:
                value = getattr(model_instance, fieldname)
            except AttributeError:
                pass
            else:
                if value:
                    query = query & Q(**{fieldname: value})
        return self.model_class.objects.filter(query)

    def _check_persistence(self, instance, persistence):
        """Returns a number of how many records fulfill the
        persistence criterion."""
        if not persistence:
            unique_fields = get_unique_fields(instance)
            if unique_fields:
                persistence = unique_fields
            else:
                return 0, None
        qs = self._get_persistence_query(instance, persistence)
        return qs.count(), qs

    def _assign_related(self, instance, rel_inst_dic):
        """Assign related instances after saving."""
        for key, item in rel_inst_dic.iteritems():
            try:
                getattr(instance, key).add(*item)
            except ValueError:
                pass

    def create_in_db(self, instance, persistence_qs):
        """Creates entry in DB."""
        if self.create:
            instance.clean_fields()
            instance.save()
            self.res['created'] = True
            return instance
        # TODO: work on error handling
        # else:
        #    raise ValidationError(
        #       'Record does not exists and create flag is False')

    def update_in_db(self, instance, persistence_qs):
        if self.update:
            dic = model_to_dict(instance)
            for key in dic.copy():
                field_type = instance._meta.get_field(
                    key).get_internal_type()
                # TODO make this more elegant
                if (
                    field_type == 'ManyToManyField' or
                    key not in self.dic and
                    key != self.hashfield
                ):
                    del dic[key]
            persistence_qs.update(**dic)
            self.res['exists'] = True
            self.res['updated'] = True
        else:
            self.res['exists'] = True
        return persistence_qs[0]

    def prepare(self, dic):
        """Basic dic to model conversion works only for models without relational
        field type. Subclass for more complicated preparations."""
        return self.model_class(**dic)

    def get_instance(self):
        """Create or get instance and add it to the database and create
        relationships."""
        model_instance = self.prepare(self.dic)
        self.res = {'updated': False, 'created': False, 'exists': False}
        if model_instance:
            if model_instance.pk:
                self.res['exists'] = True
                return model_instance
            if hasattr(model_instance, self.hashfield):
                hashvalue = self.hash_instance(model_instance)
                res = self.model_class.objects.filter(
                    **{self.hashfield: hashvalue})
                if res.count() != 0:
                    self.res['exists'] = True
                    self._assign_related(res[0], self.related_instances)
                    return res[0]
                setattr(model_instance, self.hashfield, hashvalue)
            count, qs = self._check_persistence(
                model_instance, self.persistence)
            try:
                model_instance = [
                    self.create_in_db, self.update_in_db][count](
                        model_instance, qs)
            except IndexError:
                self.res['rejected'] = True
                return model_instance
            self._assign_related(model_instance, self.related_instances)
            return model_instance


class InstanceGenerator(BaseInstanceGenerator):
    """Instance generator that can take care of foreign key and many-to-many-
    relationships as well as deal with other field attributes."""

    def _prepare_field(self, field, value):
        return value

    def _prepare_fk(self, field, value):
        return FkInstanceGenerator(field, value).get_instance()

    def _prepare_m2m(self, field, value):
        if isinstance(value, list):
            # defer assignment of related instances until instance
            # creation is finished
            self.related_instances[field.name] = []
            for entry in value:
                generator = RelInstanceGenerator(field, entry)
                self.related_instances[field.name].append(
                    generator.get_instance())

    def _prepare_date(self, field, value):
        if not (field.auto_now or field.auto_now_add):
            formfield = DateTimeField()
            return formfield.clean(value)

    def _prepare_text(self, field, value):
        if not isinstance(value, (str, unicode)):
            ret = unicode(value)
        else:
            ret = value
        if hasattr(field, 'max_length'):
            ret = ret[0:field.max_length]
        return ret

    preparations = {
        'ForeignKey': _prepare_fk,
        'ManyToManyField': _prepare_m2m,
        'DateTimeField': _prepare_date,
        'GeometryField': _prepare_field,
        'CharField': _prepare_text,
        'TextField': _prepare_text
    }

    def prepare(self, dic):
        if isinstance(dic, self.model_class):
            return dic
        model_instance = self.model_class()
        fieldnames = model_instance._meta.get_all_field_names()
        for fieldname in fieldnames:
            if fieldname not in dic:
                continue
            field = model_instance._meta.get_field(fieldname)
            fieldtype = field.get_internal_type()
            try:
                fieldvalue = self.preparations[fieldtype](
                    self, field, dic[fieldname])
            except KeyError:
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
