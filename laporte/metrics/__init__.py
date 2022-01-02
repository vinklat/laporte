# -*- coding: utf-8 -*-
'''
Prometheus metrics containers and decorators
'''

import logging
from operator import itemgetter
from time import time
from functools import wraps
from laporte.version import app_name

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())


class PrometheusMetrics:
    '''
    Prometheus metrics containers and decorators
    '''
    def __init__(self):
        self.counters = {}
        self.summaries = {}

    def func_measure(self,
                     prefix=app_name,
                     name='duration',
                     suffix='seconds',
                     help_str='duration of the operation',
                     labels=None,
                     log=False):
        '''
        Update duration (summary) of any function with this decorator is called.

        Args:
            prefix (str): single-word prefix relevant to the domain the metric belongs to
            name (str): represent a measured metric
            suffix (str): describing the unit, in plural form
            help_str (str): help_str string will aid users track back to what the metric was
            labels (dict): to differentiate the characteristics of the thing that is being measured
            log (bool): log measured value to python logger (loglevel INFO)
        Returns:
            Decorator.
        '''
        if labels is None:  # because {} is dangerous default value
            labels = {}

        def decorator(func):
            @wraps(func)
            def _time_it(*args, **kwargs):
                start_t = time()

                try:
                    return func(*args, **kwargs)
                finally:
                    metric_name = f'{prefix}_{name}_{suffix}'
                    label_keys = str(list(map(itemgetter(0), labels.items())))
                    label_values = str(list(map(itemgetter(1), labels.items())))
                    metric_id = metric_name + label_keys

                    if metric_id not in self.summaries:
                        self.summaries[metric_id] = {}

                    if label_values not in self.summaries[metric_id]:
                        self.summaries[metric_id][label_values] = {
                            'count': 0,
                            'sum': 0.0,
                            'labels': labels,
                            'help_str': help_str
                        }

                    duration = time() - start_t
                    self.summaries[metric_id][label_values]['count'] += 1
                    self.summaries[metric_id][label_values]['sum'] += duration
                    if log:
                        logging.debug("duration %s %s: %0.4fs", metric_name, labels,
                                      duration)

            return _time_it

        return decorator

    def func_count(self,
                   step=1,
                   prefix=app_name,
                   name='counter',
                   suffix='total',
                   help_str='number of operation calls',
                   labels=None,
                   log=False):
        '''
        Update number of times any function with this decorator is called.

        Args:
            prefix (str): single-word prefix relevant to the domain the metric belongs to
            name (str): represent a measured metric
            suffix (str): counter has _total as a suffix in addition to the metric unit
            help_str (str): help_str string will aid users track back to what the metric was
            labels (dict): to differentiate the characteristics of the thing that is being measured
            log (bool): log measured value to python logger (loglevel INFO)
        Returns:
            Decorator.
        '''

        if labels is None:  # because {} is dangerous default value
            labels = {}

        def decorator(func):
            @wraps(func)
            def _counter_inc(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                finally:
                    self.counter_inc(step=step,
                                     prefix=prefix,
                                     name=name,
                                     suffix=suffix,
                                     labels=labels,
                                     help_str=help_str,
                                     log=log)

            return _counter_inc

        return decorator

    def counter_inc(self,
                    step=1,
                    prefix=app_name,
                    name='counter',
                    suffix='total',
                    help_str='number of operation calls',
                    labels=None,
                    log=False):
        '''
        Incremet the accumulating counter.

        Args:
            prefix (str): single-word prefix relevant to the domain the metric belongs to
            name (str): represent a measured metric
            suffix (str): counter has _total as a suffix in addition to the metric unit
            help_str (str): help_str string will aid users track back to what the metric was
            labels (dict): to differentiate the characteristics of the thing that is being measured
            log (bool): log measured value to python logger (loglevel INFO)
        Returns:
            None.
        '''

        if labels is None:  # because {} is dangerous default value
            labels = {}

        metric_name = f'{prefix}_{name}_{suffix}'
        label_keys = str(list(map(itemgetter(0), labels.items())))
        label_values = str(list(map(itemgetter(1), labels.items())))
        metric_id = metric_name + label_keys

        if metric_id not in self.counters:
            self.counters[metric_id] = {}

        if label_values not in self.counters[metric_id]:
            self.counters[metric_id][label_values] = {
                'total': 0,
                'labels': labels,
                'help_str': help_str
            }

        self.counters[metric_id][label_values]['total'] += step
        if log:
            logging.debug("total count of %s %s: %f", metric_name, labels,
                          self.counters[metric_id][label_values]['total'])


metrics = PrometheusMetrics()
