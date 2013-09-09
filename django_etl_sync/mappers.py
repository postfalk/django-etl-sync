# python 3 preparations
from __future__ import print_function

# python
import os
import warnings
import unicodecsv as csv
from datetime import datetime

from django.conf import settings
from bee.django_etl_sync.readers import ShapefileReader
from bee.django_etl_sync.generators import InstanceGenerator


def replace_empty_string_with_none(dic):
    """
    Replaces empty values in the csv with None.
    """
    for k in dic:
        try:
            dic[k] = None if dic[k].replace(' ', '') == '' else dic[k]
        except AttributeError:
            pass
    return dic


class Mapper(object):
    """
    Generic mapper object for ETL. Create reader_class for file formats other
    than csv tab-delimited.
    """
    reader_class = None
    model_class = None
    filename = None
    encoding = 'utf-8'
    slice_begin = None
    slice_end = None
    default_values = {}
    logfile = None
    create_new = True
    update = True
    create_foreign_key = True
    persistence_definition = ['record']
    message = 'Data Extraction'

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            if hasattr(self, k):
                setattr(self, k, kwargs[k])
            else:
                warnings.warn('Invalid keyword argument for Mapper '
                              'will be ignored.')

            if not self.encoding or self.encoding == '':
                self.encoding = 'utf-8'

    def is_valid(dictionary):
        """
        Overwrite this class with conditions under
        which a record will be accepted or rejected.
        """
        return True

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
        dictionary = replace_empty_string_with_none(dictionary)
        return dic

    def load(self):
        """
        Loads data into database using model and Django ORM.
        """
        start = datetime.now()
        filename = os.path.join(settings.MEDIA_ROOT, self.filename)

        print('Opening {0} using {1}'.format(filename, self.encoding))

        logfilename = os.path.join(settings.MEDIA_ROOT, '{0}.{1}.log'.format(
            self.filename, start.date()))

        with open(filename, 'r') as sourcefile, open(logfilename, 'w') as self.logfile:

            print('Data extraction started {0}\n\nStart line: {1}\nEnd line {2}'.format(
                start, self.slice_begin, self.slice_end), file=self.logfile)

            counter = 0
            create_counter = 0
            update_counter = 0
            reject_counter = 0

            if hasattr(settings, 'ETL_FEEDBACK'):
                feedbacksize = settings.ETL_FEEDBACK
            else:
                feedbacksize = 5000

            if not self.reader_class:
                reader = csv.DictReader(sourcefile, delimiter='\t',
                    quoting=csv.QUOTE_NONE)
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
                    print('Text decoding error in line {0} => rejected'.format(
                        counter), file=self.logfile)
                    reject_counter += 1
                    continue
                # TODO: Generalize error handling for various readers
                except csv.Error:
                    print('CSV error (blank line?) in '.format(
                        counter), file=self.logfile, end='')
                    reject_counter += 1
                    continue
                except StopIteration:
                    break

                if self.slice_end and counter > self.slice_end:
                    break

                dic = self.transform(csv_dic)

                # remove keywords conflicting with Django model
                if 'id' in dic:
                    del dic['id']

                if self.is_valid(dic):
                    generator = InstanceGenerator(self.model_class, dic, persistence=['record'])
                    instance = generator.get_instance()
                    result = generator.res
                else:
                    reject_counter += 1

                create_counter += result['created']
                update_counter += result['updated']
                reject_counter += result['rejected']

                if result['rejected']:
                    print('line {0} ==> rejected\n{1}\n'.format(
                        counter, csv_dic), file=self.logfile)

                if counter % feedbacksize == 0:
                    print('{0} {1} processed in {2}, {3},'
                        ' {4} created, {5} updated, {6} rejected'.format(
                        self.message, feedbacksize, datetime.now() - start,
                        counter, create_counter,
                        update_counter, reject_counter))
                    start = datetime.now()
                    self.logfile.flush()

            print('\nData extraction finished {0}\n{1}'
                'created\n{2} updated\n{3} rejected\n'.format(start,
                create_counter, update_counter, reject_counter),
                file=self.logfile)
