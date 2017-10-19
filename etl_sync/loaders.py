from __future__ import print_function
from backports import csv
from builtins import str as text
import io
import os
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from etl_sync.generators import InstanceGenerator
from etl_sync.transformations import Transformer


def get_logfilename(filename):
    ret = None
    if isinstance(filename, (text, str)):
        ret = os.path.join(
            os.path.dirname(filename), '{0}.{1}.log'.format(
            filename, datetime.now().strftime('%Y-%m-%d')))
    return ret


def create_logfile(filename=None):
    if filename:
        return open(filename, 'w')
    else:
        return None


def get_logfile(filename=None, logfilename=None):
    if not logfilename:
        logfilename = get_logfilename(filename)
    return create_logfile(logfilename)


class FeedbackCounter(object):
    """
    Keeps track of the ETL process and provides feedback.
    """

    def __init__(self, counter=0):
        self.counter = counter
        self.rejected = 0
        self.created = 0
        self.updated = 0
        self.starttime = datetime.now()
        self.feedbacktime = self.starttime
        self.message = (
            'Extraction from {filename}:\n{records} records processed '
            'in {time}, {total}: {created} created, {updated} updated, '
            '{rejected} rejected.')

    def feedback(self, **kwargs):
        """
        Print feedback.
        """
        dic = {
            'filename': str(kwargs.get('filename')),
            'records': kwargs.get('records'),
            'time': datetime.now()-self.feedbacktime,
            'total': self.counter,
            'created': self.created,
            'updated': self.updated,
            'rejected': self.rejected}
        print(self.message.format(**dic))
        self.feedbacktime = datetime.now()

    def increment(self):
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
        if res == 'created':
            self.create()
        elif res == 'updated':
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
    Context manager, creates the reader and handles files or other
    sources. This is necessary because parameters to CSVDictReader
    needs to be set on initialization.

    Args:
        source (file, file-like object, or str)
        reader_class (CSVReader or duck-typed Reader class)
        reader_kwargs (dic): Whatever needs to be passed on to the reaader
        options (dic): custom options that need to be passed through to
            reader

    Return reader instance.
    """

    def __init__(self, source, reader_class=csv.DictReader,
                 reader_kwargs={
                    'delimiter': u'\t', 'quoting': csv.QUOTE_NONE},
                 options={}):
        self.source = source
        self.options = options
        self.reader_class = reader_class or csv.DictReader
        self.reader_kwargs = reader_kwargs or {
            'delimiter': u'\t', 'quoting': csv.QUOTE_NONE}

    def __enter__(self):
        """
        Checks whether source is file object as required by csv.Reader.
        Implement file handling in reader class. This approach allows for
        non-text data sources (see e.g. OGRReader). If self.source is not
        a file or file-like object and cannot be converted in one by opening,
        we pass self.source on. In that case the reader_class needs to make
        sense of it. This is necessary, i.e. if the source is a .gdb
        represented as a folder or an url representing an API end point.
        """
        if hasattr(self.source, 'read'):
            fil = self.source
        else:
            try:
                fil = io.open(self.source)
            except IOError:
                return self.source
        return self.reader_class(fil, **self.reader_kwargs)

    def __exit__(self, type, value, traceback):
        try:
            self.fil.close()
        except (AttributeError, IOError):
            pass


class Logger(object):
    """Class that holds the logger messages."""
    start_message = (
        'Data extraction started {start_time}\n\nStart line: '
        '{slice_begin}\nEnd line: {slice_end}\n')
    reader_error_message = (
        'Text decoding or CSV error in line {0}: {1} => rejected')
    instance_error_message = (
        'Instance generation error in line {0}: {1} => rejected')
    transformation_error_message = (
        'Transformation error in line {0}: {1} => rejected')

    def __init__(self, logfile):
        self.logfile = logfile

    def log(self, txt):
        """
        Log to log file or to stdout if self.logfile=None
        """
        print(text(txt), file=self.logfile)

    def log_start(self, options):
        self.log(self.start_message.format(**options))

    def log_reader_error(self, line, error):
        self.log(self.reader_error_message.format(line, text(error)))

    def log_transformation_error(self, line, error):
        self.log(self.transformation_error_message.format(line, text(error)))

    def log_instance_error(self, line, error):
        self.log(self.instance_error_message.format(line, text(error)))

    def close(self):
        if self.logfile:
            self.logfile.close()


class Loader(object):
    """
    Generic mapper object for ETL.
    """
    transformer_class = Transformer
    reader_class = csv.DictReader
    reader_kwargs = {'delimiter': u'\t', 'quoting': csv.QUOTE_NONE}
    generator_class = InstanceGenerator
    model_class = None
    persistence = []

    def __init__(self, source, model_class=None, options={}):
        self.source = source
        self.options = options
        self.model_class = model_class or self.model_class
        self.logfilename = options.get('logfilename')
        self.feedbacksize = options.get('feedbacksize', 5000)
        self.logfile = get_logfile(
            filename=self.source, logfilename=self.logfilename)
        self.extractor = Extractor(
            self.source, self.reader_class, self.reader_kwargs, options=options)
        self.slice_begin = options.get('slice_begin', 0)
        self.slice_end = options.get('slice_end')
        self.generator = self.generator_class(
            self.model_class, persistence=self.persistence, options=options)
        self.options = options

    def feedback_hook(self, counter):
        """
        Create actions that will be triggered after the number of records
        defined in self.feedbacksize. This can be used to store a file position
        to a database to continue a load later.

        Returns:
            Boolean: Must be True otherwise load operation will be
            aborted.

        """
        return True

    def feedback(self, counter):
        if counter.counter % self.feedbacksize == 0:
            counter.feedback(
            filename=self.source, records=self.feedbacksize)
            if not self.feedback_hook(counter.counter):
                raise StopIteration

    def reader_reject(self, counter, logger, e):
        logger.log_reader_error(counter.counter, e)
        counter.reject()
        self.feedback(counter)

    def transformation_reject(self, counter, logger, e):
        logger.log_transformation_error(counter.counter, e)
        counter.reject()
        self.feedback(counter)

    def generator_reject(self, counter, logger, e):
        logger.log_instance_error(counter.counter, e)
        counter.reject()
        self.feedback(counter)

    def process(self, extractor, counter, logger):
        """
        This is broken out from below and should be better
        organized.
        """

        try:
            dic = extractor.next()
        except (UnicodeDecodeError, csv.Error) as e:
            self.reader_reject(counter, logger, e)
            return

        defaults = self.options.get('defaults') or {}
        transformer = self.transformer_class(dic, defaults=defaults)
        try:
            if transformer.is_valid():
                dic = transformer.cleaned_data
            else:
                raise ValidationError('Transformer did not return valid data')
        except (ValidationError, ValueError, IndexError,
                KeyError) as e:
            self.transformation_reject(counter, logger, e)
            return

        try:
            self.generator.get_instance(dic)
        except (ValidationError, IntegrityError, DatabaseError,
                ValueError) as e:
            self.generator_reject(counter, logger, e)
            return

        counter.use_result(self.generator.res)
        self.feedback(counter)


    def load(self):
        """
        Loads data into database using Django models and error logging.
        """
        print('Opening {0}'.format(self.source))
        logger = Logger(self.logfile)
        logger.log_start({
            'start_time': datetime.now().strftime('%Y-%m-%d'),
            'slice_begin': self.slice_begin,
            'slice_end': self.slice_end})
        counter = FeedbackCounter()

        with self.extractor as extractor:

            while self.slice_begin and self.slice_begin > counter.counter:
                extractor.next()
                counter.increment()

            while not self.slice_end or self.slice_end >= counter.counter:
                try:
                    self.process(extractor, counter, logger)
                except StopIteration:
                    break

            if self.generator.finalize():
                logger.log(counter.finished())

            logger.close()
