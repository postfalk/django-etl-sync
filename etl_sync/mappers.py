from __future__ import print_function
from django.core.exceptions import ValidationError
import os
import warnings
import unicodecsv as csv
from datetime import datetime
from django.conf import settings
from etl_sync.generators import InstanceGenerator


class Mapper(object):
    """
    Generic mapper object for ETL. Create reader_class for file formats other
    than tab-delimited CSV.
    """
    reader_class = None
    model_class = None
    filename = None
    encoding = 'utf-8'
    slice_begin = None
    slice_end = None
    default_values = {}
    create_new = True
    update = True
    create_foreign_key = True
    etl_persistence = ['record']
    message = 'Data Extraction'
    result = None
    feedbacksize = 5000
    logfile = None
    forms = []

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            if hasattr(self, k):
                setattr(self, k, kwargs[k])
            else:
                warnings.warn('Invalid keyword argument for Mapper '
                              'will be ignored.')
            if not self.encoding or self.encoding == '':
                self.encoding = 'utf-8'
            if hasattr(settings, 'ETL_FEEDBACK'):
                self.feedbacksize = settings.ETL_FEEDBACK

    def validate(self, dic):
        """
        Raise ValidationError here.
        """
        pass

    def log(self, text):
        """
        Log to logfile or to stdout if self.logfile=None
        """
        print(text, file=self.logfile)

    def remap(self, dic):
        """
        Use this method for remapping dictionary keys.
        """
        return dic

    def process_forms(self, dic):
        """
        Processes a list of forms.
        """
        for form in self.forms:
            frm = form(dic)
            if frm.is_valid():
                dic.update(frm.cleaned_data)
            else:
                for error in frm.errors['__all__']:
                    raise ValidationError(error)
        return dic

    def transform(self, dic):
        """
        Additional transformations not covered by remap and forms.
        """
        return dic

    def apply_defaults(self, dictionary):
        """
        Adds defaults to the dictionary.
        """
        if type(self.default_values) is dict:
            dic = self.default_values.copy()
        else:
            dic = {}
        dic = dict(dic.items() + dictionary.items())
        return dic

    def full_transform(self, dic):
        """
        Runs all four transformation steps.
        """
        dic = self.apply_defaults(dic)
        dic = self.remap(dic)
        dic = self.transform(dic)
        dic = self.process_forms(dic)
        self.validate(dic)
        return dic

    def load(self):
        """
        Loads data into database using Django models and error logging.
        """
        start = datetime.now()
        print('Opening {0} using {1}'.format(self.filename, self.encoding))
        logfilename = os.path.join(
            os.path.dirname(self.filename), '{0}.{1}.log'.format(
                self.filename, start.date()))
        with open(
            self.filename, 'r') as sourcefile, open(
                logfilename, 'w') as self.logfile:
            self.log(
                'Data extraction started {0}\n\nStart line: '
                '{1}\nEnd line: {2}\n'.format(
                    start, self.slice_begin, self.slice_end))
            counter = 0
            create_counter = 0
            update_counter = 0
            reject_counter = 0
            if self.reader_class:
                reader = self.reader_class(sourcefile)
            else:
                reader = csv.DictReader(
                    sourcefile, delimiter='\t', quoting=csv.QUOTE_NONE)
            while self.slice_begin and self.slice_begin > counter:
                counter += 1
                reader.next()
            while not self.slice_end or self.slice_end > counter:
                counter += 1
                try:
                    csv_dic = reader.next()
                except (UnicodeDecodeError, csv.Error):
                    self.log(
                        'Text decoding or CSV error in line {0} '
                        '=> rejected'.format(counter))
                    reject_counter += 1
                    continue
                except StopIteration:
                    break
                try:
                    dic = self.full_transform(csv_dic)
                except ValidationError, e:
                    self.log('Validation error in line {0}: {1} '
                             '=> rejected'.format(counter, str(e)))
                    reject_counter += 1
                    continue
                # remove keywords conflicting with Django model
                # TODO: I think that is done in several places now
                # determine the one correct one and get rid of the others
                if 'id' in dic:
                    del dic['id']
                generator = InstanceGenerator(
                    self.model_class, dic,
                    persistence=self.etl_persistence)
                try:
                    generator.get_instance()
                except Exception, e:
                    self.log('Error in line {0}: {1} => rejected'.format(
                        counter, str(e)))
                    reject_counter += 1
                    continue
                create_counter += generator.res['created']
                update_counter += generator.res['updated']
                if counter % self.feedbacksize == 0:
                    print('{0} {1} processed in {2}, {3},'
                          ' {4} created, {5} updated, {6} rejected'.format(
                              self.message, self.feedbacksize,
                              datetime.now() - start,
                              counter, create_counter,
                              update_counter, reject_counter))
                    start = datetime.now()
            self.log(
                '\nData extraction finished {0}\n\n{1} '
                'created\n{2} updated\n{3} rejected'.format(
                    start, create_counter, update_counter,
                    reject_counter))
        self.result = 'loaded'
