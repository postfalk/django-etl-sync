"""
Classes that generate model instances from dictionaries.
"""
from __future__ import print_function
from hashlib import md5
from django.db.models import Q
from django.db import IntegrityError, DatabaseError
from django.forms.models import model_to_dict
from django.forms import DateTimeField, ValidationError


def indent_log(message):
    """Indent log messages from subroutines."""
    if message:
        return '  ' + message.replace('\n', '\n  ')


def append_log(log, message):
    """Append messages to log."""
    if message:
        return '{0}\n{1}'.format(log, message)


def get_unique_fields(model_class):
    """
    Get model fields with attribute unique.
    """
    ret = []
    for field in model_class._meta.fields:
        if field.unique:
            ret.append(field.name)
    return ret


class BaseInstanceGenerator(object):
    """
    Generates, evaluates, and saves instances from dictionary.
    """
    hashfield = 'md5'

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
        """
        Method for hashing.
        """
        fields = instance._meta.fields
        out = u''
        for field in fields:
            if field.name not in [self.hashfield, u'id', u'modified']:
                try:
                    value = unicode(getattr(instance, field.name))
                except TypeError:
                    pass
                else:
                    if value:
                        out = out + value
        ret = md5(out.encode('utf-8')).hexdigest()
        return ret

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

    def assign_related(self, instance, rel_inst_dic):
        """
        Assign related instances (use after saving).
        """
        for key, item in rel_inst_dic.iteritems():
            try:
                getattr(instance, key).add(*item)
            except ValueError:
                pass

    def get_instance(self):
        """
        Create or get instance and add it to the database and create
        relationships.
        """
        model_instance = self.prepare(self.dic)

        if not model_instance:
            self.res['rejected'] = True
            return None

        if model_instance.pk:
            self.res['exists'] = True
            return model_instance

        if hasattr(model_instance, self.hashfield):
            hashvalue = self.hash_instance(model_instance)
            res = self.model_class.objects.filter(
                **{self.hashfield: hashvalue})
            if res.count() != 0:
                self.res['exists'] = True
                self.assign_related(res[0], self.related_instances)
                return res[0]
            setattr(model_instance, self.hashfield, hashvalue)

        if self.persistence:
            result = self.get_persistence_query(model_instance,
                                                self.persistence)
            record_count = result.count()
        else:
            unique_fields = get_unique_fields(model_instance)
            # redundant?
            if 'id' in unique_fields:
                unique_fields.remove('id')
            if len(unique_fields) > 0:
                result = self.get_persistence_query(
                    model_instance, unique_fields)
                record_count = result.count()
            else:
                record_count = 0

        if record_count == 0:
            if self.create:
                try:
                    model_instance.clean_fields()
                except ValidationError:
                    self.res['rejected'] = True
                else:
                    try:
                        model_instance.save()
                    except IntegrityError:
                        self.res['rejected'] = True
                    else:
                        self.res['created'] = True
            self.assign_related(model_instance, self.related_instances)

        elif record_count == 1:
            if self.update:
                dic = model_to_dict(model_instance)
                for key in dic.copy():
                    field_type = model_instance._meta.get_field(
                        key).get_internal_type()
                    # TODO make this more elegant
                    if (
                        field_type == 'ManyToManyField' or
                        key not in self.dic and
                        key != self.hashfield
                    ):
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

        self.assign_related(model_instance, self.related_instances)
        return model_instance


class InstanceGenerator(BaseInstanceGenerator):
    """
    Instance generator that can take of foreign key and many-to-many-
    relationships.
    """

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
            fieldvalue = None

            if fieldtype == 'ForeignKey':
                fieldvalue = FkInstanceGenerator(
                    field, dic[fieldname]).get_instance()

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
                if dic.get(fieldname):
                    if not isinstance(dic[fieldname], str):
                        fieldvalue = unicode(dic[fieldname])
                    else:
                        fieldvalue = dic[fieldname]
                    if hasattr(field, 'max_length'):
                        fieldvalue = fieldvalue[0:field.max_length]
                else:
                    fieldvalue = ''

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
