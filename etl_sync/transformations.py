"""Provides class to do transformations between data extraction
and loading. Keep compatible to Django's Form class so that
simple transformations can be done with forms."""
from django.core.exceptions import ValidationError


class Transformer(object):
    """Base transformer."""
    forms = []

    def __init__(self, dic, defaults={}):
        self.dic = dic
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

    def validate(self, dic):
        """Raise ValidationError here."""
        pass

    def remap(self, dic):
        """Use this method for remapping dictionary keys."""
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
        dic = self.transform(dic)
        self.validate(dic)
        return dic

    def clean(self, dic):
        """For compatibility with Django's form class.
        TODO: consolidate."""
        return self.full_transform(dic)

    def is_valid(self):
        try:
            self.cleaned_data = self.clean(self.dic)
            return True
        except ValidationError:
            return False
