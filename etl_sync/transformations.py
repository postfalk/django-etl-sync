import re
from django.core.exceptions import ValidationError


class Transformer(object):
    """Base transformer. Django forms can be used instead.
    This class contains only the bare minimum of methods
    and is able to process a list of forms."""
    forms = []
    error = None
    # dictionary of mappings applied in remap
    mappings = {}
    # dictionary of fieldnames and regexes for invalid values
    blacklist = {}
    defaults = {}

    def __init__(self, dic, defaults={}):
        self.dic = dic
        if defaults:
            self.defaults = defaults

    def _process_forms(self, dic):
        """Processes a list of forms."""
        for form in self.forms:
            frm = form(dic)
            if frm.is_valid():
                dic.update(frm.cleaned_data)
            else:
                for error in frm.errors['__all__']:
                    raise ValidationError(error)
        return dic

    def _apply_defaults(self, dictionary):
        """Adds defaults to the dictionary."""
        if type(self.defaults) is dict:
            dic = self.defaults.copy()
        else:
            dic = {}
        dic = dict(dic.items() + dictionary.items())
        return dic

    def check_blacklist(self, dic):
        """Raise ValidationError if value or pattern is
        black-listed."""
        for key, value in self.blacklist.iteritems():
            for v in value:
                if re.match(v, dic[key]):
                    raise ValidationError(
                        'Value {} not allowed in field {}'.format(
                            key, v))

    def validate(self, dic):
        """Raise validation errors here."""
        pass

    def remap(self, dic):
        """Use this method for remapping dictionary keys."""
        for key in self.mappings:
            dic[key] = dic[self.mappings[key]]
            del dic[self.mappings[key]]
        return dic

    def transform(self, dic):
        """Additional transformations not covered by remap and forms."""
        return dic

    def full_transform(self, dic):
        """Runs all four transformation steps."""
        # Order is important here
        dic = self.remap(dic)
        dic = self._apply_defaults(dic)
        dic = self._process_forms(dic)
        self.check_blacklist(dic)
        dic = self.transform(dic)
        self.validate(dic)
        return dic

    def clean(self, dic):
        """For compatibility with Django's form class."""
        return self.full_transform(dic)

    def is_valid(self):
        try:
            self.cleaned_data = self.clean(self.dic)
            return True
        except (ValidationError, UnicodeEncodeError), e:
            self.error = e
            return False
