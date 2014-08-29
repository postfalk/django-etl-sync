"""Classes that generate model instances from dictionaries."""
from __future__ import print_function
from hashlib import md5
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms.models import model_to_dict
from django.forms import DateTimeField


def get_unique_fields(model_class):
    """Get model fields with unique=True."""
    ret = []
    for field in model_class._meta.fields:
        if field.unique and not field.name == 'id':
            ret.append(field.name)
    return ret


def get_unambigous_field(model_class):
    """Checks whether there is a way to match a string to a
    field in ForeignKey model. Use 'name' as default."""
    ct_char = 0
    ct_uniquechar = 0
    for f in model_class._meta.fields:
        test = (f.get_internal_type() == 'CharField')
        if test and ct_char < 2:
            if f.name == 'name':
                return 'name'
            ct_char += 1
            charfield = f.name
        if f.unique and test:
            if ct_uniquechar < 2:
                ct_uniquechar += 1
                uniquecharfield = f.name
            else:
                break
    if ct_char == 1:
        return charfield
    if ct_uniquechar == 1:
        return uniquecharfield
    raise ValidationError(
        'Fk field cannot be assigned for {}'.format(model_class))


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
                except (TypeError, Exception):
                    pass
                else:
                    if value:
                        out = out + value
        ret = md5(out.encode('utf-8')).hexdigest()
        return ret

    def _check_hash(self, instance, field):
        count = 0
        qs = []
        if hasattr(instance, field):
            value = self.hash_instance(instance)
            qs = self.model_class.objects.filter(
                **{field: value})
            setattr(instance, field, value)
            count = qs.count()
        return count, qs

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
                    query = query & Q(
                        **{fieldname: value})
        return self.model_class.objects.filter(query)

    def _check_persistence(self, instance, persistence):
        """Returns the number of records that fulfill the
        persistence criterion and the queryset resulting from
        the application of the persistence criterion."""
        if not persistence:
            unique_fields = get_unique_fields(instance)
            if unique_fields:
                persistence = unique_fields
            else:
                return 0, None
        qs = self._get_persistence_query(instance, persistence)
        return qs.count(), qs

    def _assign_related(self, instance, rel_inst_dic, dic={}):
        """Assign related instances after saving the parent
        record. The instances should be fully prepared and
        clean at this point. Use the original dic to fill
        in intermediate relationship."""
        for key, lst in rel_inst_dic.iteritems():
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
            except ValueError:
                print('issue with assignment of related instances')
                # TODO: explore while lst can be None
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
            # see whether that suits us here, check whether M2M field
            # updates work as well (as they should since they are treated
            # seperately)
            persistence_qs.update(**dic)
            self.res['exists'] = True
            self.res['updated'] = True
        else:
            self.res['exists'] = True
        return persistence_qs[0]

    def prepare(self, dic):
        """Basic dictionary to model conversion. Works only for models
        without relational field types. Subclass and extend method for
        more complicated preparations."""
        return self.model_class(**dic)

    def get_instance(self):
        """Create or get instance, add it to the database,
        and create relationships."""
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
            else:
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
                        string = string + ', ' + key
                    print('Double entry found for {}'.format(string))
                    return model_instance
            self._assign_related(
                model_instance, self.related_instances, self.dic)
            return model_instance


class InstanceGenerator(BaseInstanceGenerator):
    """Instance generator that can take care of foreign key and many-to-many-
    relationships as well as deal with other field attributes."""

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

    def _prepare_boolean(self, field, value):
        if value:
            return value in [1, '1', 'True', 'true', 't']
        return False

    def _prepare_integer(self, field, value):
        if not isinstance(value, int):
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        return value

    def _prepare_float(self, field, value):
        if not isinstance(value, float):
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        return value

    preparations = {
        'ForeignKey': _prepare_fk,
        'ManyToManyField': _prepare_m2m,
        'DateTimeField': _prepare_date,
        'GeometryField': _prepare_field,
        'CharField': _prepare_text,
        'TextField': _prepare_text,
        'BooleanField': _prepare_boolean,
        'IntegerField': _prepare_integer,
        'FloatField': _prepare_float
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
            except AttributeError:
                pass
            except ValueError:
                pass
        return model_instance


class RelInstanceGenerator(InstanceGenerator):
    """Prepares related instances in M2M relationships."""

    def __init__(self, field, dic, **kwargs):
        super(RelInstanceGenerator, self).__init__(None, dic, **kwargs)
        self.model_class = field.rel.to


class FkInstanceGenerator(RelInstanceGenerator):
    """Prepares ForeignKey instances. Order of tests:
    1. Instance, 2. Dictionary, 3. Integer,
    4. Unique name or single field"""

    def __init__(self, field, dic, **kwargs):
        super(FkInstanceGenerator, self).__init__(field, dic, **kwargs)
        self.field = field
        self.related_field = field.rel.field_name
        self.update = False
        try:
            self.update = dic.get('etl_update')
        except(AttributeError):
            pass

    def prepare(self, value):
        if not value:
            return None
        if isinstance(value, self.model_class):
            return value
        else:
            if isinstance(value, dict):
                key = get_unambigous_field(self.model_class)
                fk_dic = value
                if key in fk_dic and self.related_field == 'id':
                    self.persistence = [key]
            elif isinstance(value, int):
                fk_dic = {self.related_field: value}
                self.persistence = [self.related_field]
            else:
                key = get_unambigous_field(self.model_class)
                if self.related_field == 'id':
                    fk_dic = {key: value}
                    self.persistence = [key]
                else:
                    fk_dic = {self.related_field: value}
                    self.persistence = [self.related_field]
            ret = super(FkInstanceGenerator, self).prepare(fk_dic)
        return ret
