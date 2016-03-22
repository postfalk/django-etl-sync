from __future__ import print_function
from backports import csv
from io import open
from builtins import str as text

import warnings

import os
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from django.conf import settings
from etl_sync.generators import InstanceGenerator
from etl_sync.transformations import Transformer


def get_logfilename(filename):
    if filename:
        return os.path.join(
            os.path.dirname(filename), '{0}.{1}.log'.format(
            filename, datetime.now().strftime('%Y-%m-%d')))


class FeedbackCounter(object):
    """
    Keeps track of the ETL process and provides feedback.
    """

    def __init__(self, message=None, feedbacksize=5000, counter=0):
        self.counter = counter
        self.feedbacksize = feedbacksize
        self.message = message
        self.rejected = 0
        self.created = 0
        self.updated = 0
        self.starttime = datetime.now()
        self.feedbacktime = self.starttime

    def _feedback(self):
        """
        Print feedback.
        """
        if self.counter % self.feedbacksize == 0:
            print(
                '{0} {1} processed in {2}, {3}, {4} created, {5} updated, '
                '{6} rejected'.format(
                    self.message, self.feedbacksize,
                    datetime.now()-self.feedbacktime, self.counter,
                    self.created, self.updated, self.rejected))
            self.feedbacktime = datetime.now()

    def increment(self):
        if self.counter > 0:
            self._feedback()
        self.counter += 1

    def reject(self):
        self.rejected += 1
        self.increment()

    def create(self):
        self.created += 1
        self.increment()

    def update(self):
        self.updated += 1
        self.increment()

    def use_result(self, res):
        """
        Use feedback from InstanceGenerator to set counters.
        """
        if res.get('created'):
            self.create()
        elif res.get('updated'):
            self.update()
        else:
            self.increment()

    def finished(self):
        """
        Provides a final message.
        """
        return (
            'Data extraction finished {0}\n\n{1} '
            'created\n{2} updated\n{3} rejected'.format(
                datetime.now(), self.created, self.updated,
                self.rejected))


class Extractor(object):
    """
    Context manager that creates the reader and handles files.
    """
    reader_class = csv.DictReader
    reader_kwargs = {'delimiter': u'\t', 'quoting': csv.QUOTE_NONE}
    encoding = 'utf-8'
    logname = None

    def __init__(self, filename, logname=None, reader_class=None,
                 reader_kwargs = {}, encoding=None):
        self.filename = filename
        self.logname = self.logname or logname or get_logfilename(filename)  # deprecate kwarg
        self.reader_class = self.reader_class or reader_class  # deprecate kwarg
        self.reader_kwargs = self.reader_kwargs or reader_kwargs  # deprecate kwarg
        self.encoding = self.encoding or encoding  # deprecate kwarg
        self.fil = None
        self.logfile = None

    def _log(self, tex):
        """
        Log to logfile or to stdout if self.logfile=None
        """
        print(text(tex), file=self.logfile)

    def __enter__(self):
        """
        Passes file object to reader class as required by csv.Reader.
        On failure pass path to reader class and see whether it can be
        handled there. Allows for non-text data sources or directories.
        """
        self.logfile = open(self.logname, 'w')
        try:
            self.fil = open(self.filename, 'r')
        except IOError:
            reader = self.reader_class(self.filename, **self.reader_kwargs)
        else:
            reader = self.reader_class(self.fil, **self.reader_kwargs)
        reader.log = self._log
        return reader

    def __exit__(self, type, value, traceback):
        for filehandle in [self.fil, self.logfile]:
            try:
                filehandle.close()
            except (AttributeError, IOError):
                pass


class FileReaderLogManager(Extractor):
    """Deprecate, use for compatibility"""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            'FileReaderLogManager will be deprecated in release 1.0 '
            'use Extractor instead.', DeprecationWarning)
        super(FileReaderLogManager, self).__init__(*args, **kwargs)


class Loader(object):
    """
    Generic mapper object for ETL.
    """
    reader_class = csv.DictReader # to be deprecated
    reader_kwargs = {'delimiter': u'\t', 'quoting': csv.QUOTE_NONE} # to be deprecated
    transformer_class = Transformer
    extractor_class = Extractor
    generator_class = InstanceGenerator
    model_class = None
    filename = None
    encoding = 'utf-8' # to be deprecated
    slice_begin = 0
    slice_end = None
    defaults = {} # to be deprecated in 1.0, set in Transformer class
    create_new = True
    update = True
    create_foreign_key = True
    etl_persistence = ['record']
    message = 'Data Extraction'
    result = None
    feedbacksize = 5000
    logfile = None
    logfilename = None
    forms = []

    def __init__(self, *args, **kwargs):
        for k in kwargs:
            try:
                setattr(self, k, kwargs[k])
                will_be_deprecated = {
                    'defaults': 'Transformer',
                    'reader_class': 'Extractor',
                    'reader_kwargs': 'Extractor',
                    'encoding': 'Extractor',
                    'logfile': 'Extractor',
                    'logfilename': 'Extractor',
                    'create_new': 'Generator',
                    'update': 'Generator',
                    'create_foreign_key': 'Generator',
                    'message': 'Extractor'}
                if k in will_be_deprecated:
                    warnings.warn(
                        'The {}= kwarg for the Mapper class will '
                        'be deprecated in release 1.0. Set values '
                        'in subclass of {}.'.format(k, will_be_deprecated[k]),
                        DeprecationWarning)
            except AttributeError:
                warnings.warn(
                    'Invalid keyword argument for Mapper will be ignored.')
        try:
            self.feedbacksize = getattr(settings, 'ETL_FEEDBACK', 5000)
        except:
            pass
        self.logfilename = get_logfilename(self.filename)

    def _log(self, text):
        """
        Log to log file or to stdout if self.logfile=None
        """
        print(text, file=self.logfile)

    def load(self):
        """
        Loads data into database using Django models and error logging.
        """
        print('Opening {0} using {1}'.format(self.filename, self.encoding))
        with self.extractor_class(self.filename,
                       logname=self.logfilename,
                       reader_class=self.reader_class,
                       reader_kwargs=self.reader_kwargs,
                       encoding=self.encoding) as extractor:
            extractor.log(
                'Data extraction started {0}\n\nStart line: '
                '{1}\nEnd line: {2}\n'.format(
                    datetime.now().strftime(
                        '%Y-%m-%d'), self.slice_begin, self.slice_end))
            counter = FeedbackCounter(
                feedbacksize=self.feedbacksize, message=self.message)
            while self.slice_begin and self.slice_begin > counter.counter:
                extractor.next()
                counter.increment()
            while not self.slice_end or self.slice_end >= counter.counter:
                try:
                    csv_dic = extractor.next()
                except (UnicodeDecodeError, csv.Error):
                    extractor.log(
                        'Text decoding or CSV error in line {0} '
                        '=> rejected'.format(counter.counter))
                    counter.reject()
                    continue
                except StopIteration:
                    extractor.log('End of file.')
                    break
                transformer = self.transformer_class(csv_dic, self.defaults)
                if transformer.is_valid():
                    dic = transformer.cleaned_data
                else:
                    extractor.log(
                        'Validation error in line {0}: {1} '
                        '=> rejected'.format(
                            counter.counter, transformer.error))
                    counter.reject()
                    continue
                generator = self.generator_class(
                    self.model_class, dic,
                    persistence=self.etl_persistence)
                try:
                    generator.get_instance()
                except (ValidationError, IntegrityError, DatabaseError) as e:
                    extractor.log('Error in line {0}: {1} => rejected'.format(
                        counter.counter, str(e)))
                    counter.reject()
                    continue
                else:
                    counter.use_result(generator.res)
            extractor.log(counter.finished())
        return 'finished'
