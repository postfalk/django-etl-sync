from __future__ import print_function
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

    def is_valid(self, dictionary):
        """Overwrite this class with conditions under which a record will be
        accepted or rejected."""
        return True

    def log(self, text):
        print(text, file=self.logfile)

    def transform(self, dictionary):
        """
        Performs transformations on the dictionary loaded from csv line.
        The output keys need to match model destination attribute names.
        Keys not present as model fields will be ignored in load.
        Extend this method for custom transformations.
        """
        if type(self.default_values) is dict:
            dic = self.default_values.copy()
        else:
            dic = {}
        dic = dict(dic.items() + dictionary.items())
        return dic

    def load(self):
        """
        Loads data into database using model and Django ORM.
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
                '{1}\nEnd line {2}'.format(
                    start, self.slice_begin, self.slice_end))
            counter = 0
            create_counter = 0
            update_counter = 0
            reject_counter = 0
            if not self.reader_class:
                reader = csv.DictReader(
                    sourcefile, delimiter='\t', quoting=csv.QUOTE_NONE)
            else:
                reader = self.reader_class(sourcefile)
            while self.slice_begin and self.slice_begin > counter:
                counter += 1
                reader.next()
            while True:
                counter += 1
                try:
                    csv_dic = reader.next()
                except UnicodeDecodeError:
                    self.log(
                        'Text decoding error in line {0} => rejected'.format(
                            counter))
                    reject_counter += 1
                    continue
                # TODO: Generalize error handling for various readers
                except csv.Error:
                    self.log(
                        'CSV error (blank line?) in '.formatst(
                            counter))
                    reject_counter += 1
                    continue
                except StopIteration:
                    break
                if self.slice_end and counter > self.slice_end:
                    break
                dic = self.transform(csv_dic)
                # remove keywords conflicting with Django model
                # TODO: I think that is done in several places now
                # determine the one correct one and get rid of the others
                if 'id' in dic:
                    del dic['id']
                result = {'created': False, 'updated': False,
                          'exists': False, 'rejected': False}
                if self.is_valid(dic):
                    generator = InstanceGenerator(
                        self.model_class, dic,
                        persistence=self.etl_persistence)
                    generator.get_instance()
                    result = generator.res
                    if generator.log:
                        self.log(generator.log)
                else:
                    reject_counter += 1
                create_counter += result['created']
                update_counter += result['updated']
                reject_counter += result['rejected']
                if result['rejected']:
                    self.log(
                        'line {0} ==> rejected\n{1}\n'.format(
                            counter, csv_dic))
                if counter % self.feedbacksize == 0:
                    print('{0} {1} processed in {2}, {3},'
                          ' {4} created, {5} updated, {6} rejected'.format(
                              self.message, self.feedbacksize,
                              datetime.now() - start,
                              counter, create_counter,
                              update_counter, reject_counter))
                    start = datetime.now()
            self.log(
                '\nData extraction finished {0}\n{1}'
                'created\n{2} updated\n{3} rejected\n'.format(
                    start, create_counter, update_counter,
                    reject_counter))
        self.result = 'loaded'
