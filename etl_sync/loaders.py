from __future__ import print_function
from backports import csv
from builtins import str as text

import io
import os
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from django.conf import settings
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
            'Extraction from {filename}:\n {records} records processed '
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
    Context manager, creates the reader and handles files. This seems
    to be necessary since arguments to CSVDictReader require to be set
    on initialization.

    Return reader instance.
    """
    reader_class = csv.DictReader
    reader_kwargs = {'delimiter': u'\t', 'quoting': csv.QUOTE_NONE}

    def __init__(self, source):
        self.source = source

    def __enter__(self):
        """
        Checks whether source is file object as required by csv.Reader.
        Implement file handling in your own reader class. Allows for
        non-text data sources or directories (see e.g. OGRReader)
        """
        if hasattr(self.source, 'read'):
            fil = self.source
        else:
            try:
                fil = io.open(self.source)
            except IOError:
                return None
        ret = self.reader_class(fil, **self.reader_kwargs)
        return ret

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
    instance_error_message = (
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
    extractor_class = Extractor
    generator_class = InstanceGenerator
    model_class = None
    filename = None # move to init
    encoding = 'utf-8' # to be deprecated
    slice_begin = 0 # move to init
    slice_end = None # move to init
    defaults = {} # to be deprecated in 1.0, set in Transformer class
    create_new = True
    update = True
    create_foreign_key = True
    etl_persistence = ['record']
    result = None
    logfilename = None

    def __init__(self, *args, **kwargs):
        self.source = kwargs.get('filename')
        self.model_class = kwargs.get('model_class') or self.model_class
        self.feedbacksize = getattr(settings, 'ETL_FEEDBACK', 5000)
        self.logfile = get_logfile(
            filename=self.source, logfilename=self.logfilename)
        self.extractor = self.extractor_class(self.source)

    def feedback_hook(self, counter):
        """Create actions that will be triggered after the number of records
        defined in self.feedbacksize. This can be used to store a file position
        to a database to continue a load later.

        Returns:
            Boolean: Must be True otherwise load operation will be
            aborted.

        """
        return True

    def load(self):
        """
        Loads data into database using Django models and error logging.
        """
        print('Opening {0} using {1}'.format(self.source, self.encoding))
        logger = Logger(self.logfile)
        counter = FeedbackCounter()

        with self.extractor as extractor:

            logger.log_start({
                'start_time': datetime.now().strftime('%Y-%m-%d'),
                'slice_begin': self.slice_begin,
                'slice_end': self.slice_end})

            while self.slice_begin and self.slice_begin > counter.counter:
                extractor.next()
                counter.increment()

            while not self.slice_end or self.slice_end >= counter.counter:

                try:
                    dic = extractor.next()
                except (UnicodeDecodeError, csv.Error) as e:
                    logger.log_reader_error(counter.counter, e)
                    counter.reject()
                    continue
                except StopIteration:
                    break

                transformer = self.transformer_class(dic)
                if transformer.is_valid():
                    dic = transformer.cleaned_data
                else:
                    logger.log_transformation_error(
                        counter.counter, transformer.error)
                    counter.reject()
                    continue

                generator = self.generator_class(
                    self.model_class, dic,
                    persistence=self.etl_persistence)
                try:
                    generator.get_instance()
                except (ValidationError, IntegrityError, DatabaseError) as e:
                    logger.log_instance_error(counter.counter, e)
                    counter.reject()
                    continue
                counter.use_result(generator.res)

                if counter.counter % self.feedbacksize == 0:
                    counter.feedback(
                        filename=self.source, records=self.feedbacksize)
                    if not self.feedback_hook(counter.counter):
                        break

            logger.log(counter.finished())
            logger.close()
