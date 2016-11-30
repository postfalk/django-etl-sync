import re
from unittest import TestCase
from etl_sync.loaders import (
    get_logfilename, FeedbackCounter)
from .utils import captured_output


class TestUtils(TestCase):

    def test_get_logfilename(self):
        logfile_path = get_logfilename(
            '/this/is/somewhere/on/the/filesystem.csv')
        self.assertTrue(
            re.match(
                r'^\/this\/is\/somewhere\/on\/the\/filesystem\.csv\.\d{4}-'
                '\d{2}-\d{2}\.log$',
                logfile_path))


class TestFeedbackCounter(TestCase):

    def test_feedbackcounter(self):
        counter = FeedbackCounter()
        self.assertEqual(counter.counter, 0)
        counter.increment()
        self.assertEqual(counter.counter, 1)
        counter.increment()
        self.assertEqual(counter.counter, 2)
        counter.reject()
        self.assertEqual(counter.counter, 3)
        self.assertEqual(counter.rejected, 1)
        counter.update()
        self.assertEqual(counter.counter, 4)
        self.assertEqual(counter.rejected, 1)
        self.assertEqual(counter.updated, 1)
        counter.create()
        self.assertEqual(counter.counter, 5)
        self.assertEqual(counter.updated, 1)
        self.assertEqual(counter.created, 1)


    def test_feedback(self):
        counter = FeedbackCounter()
        for index in range(0, 10):
            counter.create()
        with captured_output() as (out, err):
            counter.feedback(filename='test', records=10)
        print(out)

