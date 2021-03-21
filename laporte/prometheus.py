# -*- coding: utf-8 -*-
'''
Prometheus metrics containers and decorators
'''

import logging
from operator import itemgetter
from time import time
from functools import wraps
from prometheus_client.core import (InfoMetricFamily, GaugeMetricFamily,
                                    CounterMetricFamily, SummaryMetricFamily)
from .sensor import COUNTER
from .version import __version__

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

DEFAULT_PREFIX = 'laporte'

default_duration_metric = {
    'prefix': DEFAULT_PREFIX,
    'name': 'duration',
    'suffix': 'seconds',
    'help_str': 'duration of the operation'
}

default_counter_metric = {
    'prefix': DEFAULT_PREFIX,
    'name': 'counter',
    'suffix': 'total',
    'help_str': 'number of operation calls'
}

log_message_metric = {
    'prefix': DEFAULT_PREFIX,
    'name': 'log_messages',
    'suffix': 'total',
    'help_str': 'number of messages logged'
}

http_duration_metric = {
    'prefix': 'http',
    'name': 'request_duration',
    'suffix': 'seconds',
    'help_str': 'duration of http request'
}

http_requests_metric = {
    'prefix': 'http',
    'name': 'requests',
    'suffix': 'total',
    'help_str': 'number of http requests received'
}

http_responses_metric = {
    'prefix': 'http',
    'name': 'responses',
    'suffix': 'total',
    'help_str': 'number of http responses sent'
}

http_exception_responses_metric = {
    'prefix': 'http',
    'name': 'exception_responses',
    'suffix': 'total',
    'help_str': 'number of exceptions during http responses'
}

socketio_duration_metric = {
    'prefix': 'socketio',
    'name': 'event_duration',
    'suffix': 'seconds',
    'help_str': 'duration of Socket.IO event'
}


class PrometheusMetrics:
    '''
    Prometheus metrics containers and decorators
    '''
    def __init__(self):
        self.counters = {}
        self.summaries = {}

    def func_measure(self,
                     prefix=default_duration_metric['prefix'],
                     name=default_duration_metric['name'],
                     suffix=default_duration_metric['suffix'],
                     help_str=default_duration_metric['help_str'],
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
                   prefix=default_counter_metric['prefix'],
                   name=default_counter_metric['name'],
                   suffix=default_counter_metric['suffix'],
                   help_str=default_counter_metric['help_str'],
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
                    prefix=default_counter_metric['prefix'],
                    name=default_counter_metric['name'],
                    suffix=default_counter_metric['suffix'],
                    help_str=default_counter_metric['help_str'],
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

        metric_name = '{}_{}_{}'.format(prefix, name, suffix)
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

    class CustomCollector():
        def __init__(self, inner_metrics):
            self.metrics = inner_metrics

        def collect(self):

            # Laporte versison info
            families = {
                "0":
                InfoMetricFamily(DEFAULT_PREFIX,
                                 'Laporte version',
                                 value={'version': __version__})
            }

            # dump stored durations
            for metric_id, labels_data in self.metrics.summaries.items():
                for _, values_data in labels_data.items():  # unused values_key
                    count = values_data['count']
                    summ = values_data['sum']
                    labels = values_data['labels']

                    if metric_id not in families:
                        label_keys = list(map(itemgetter(0), labels.items()))
                        help_str = '{} (labels: {})'.format(
                            values_data['help_str'], ', '.join(
                                label_keys)) if label_keys else values_data['help_str']
                        met = SummaryMetricFamily(metric_id.split('[')[0],
                                                  help_str,
                                                  labels=label_keys)
                        families[metric_id] = met
                    else:
                        met = families[metric_id]

                    label_values = list(map(itemgetter(1), labels.items()))
                    met.add_metric(label_values, count, summ)

            # dump stored counters
            for metric_id, labels_data in self.metrics.counters.items():
                for _, values_data in labels_data.items():  # unused values_key
                    total = values_data['total']
                    labels = values_data['labels']

                    if metric_id not in families:
                        label_keys = list(map(itemgetter(0), labels.items()))
                        help_str = '{} (labels: {})'.format(
                            values_data['help_str'], ', '.join(
                                label_keys)) if label_keys else values_data['help_str']
                        met = CounterMetricFamily(metric_id.split('[')[0],
                                                  help_str,
                                                  labels=label_keys)
                        families[metric_id] = met
                    else:
                        met = families[metric_id]

                    label_values = list(map(itemgetter(1), labels.items()))
                    met.add_metric(label_values, total)

            # dump laporte sensors
            for sensor in self.metrics.sensors.sensor_index:
                if sensor.export_hidden:
                    continue

                for (name, metric_type, value, labels, labels_data,
                     prefix) in sensor.get_promexport_data():
                    if prefix is None:
                        metric_name = f'{DEFAULT_PREFIX}_{name}'
                    else:
                        metric_name = f'{prefix}_{name}' if prefix else name

                    uniqname = f'{metric_name}_' + '_'.join(labels)
                    if uniqname not in families:
                        help_str = 'with labels: {}'.format(', '.join(labels))
                        if metric_type == COUNTER:
                            x = CounterMetricFamily(metric_name, help_str, labels=labels)
                        else:
                            x = GaugeMetricFamily(metric_name, help_str, labels=labels)
                        families[uniqname] = x
                    else:
                        x = families[uniqname]

                    x.add_metric(labels_data, value)

            for family in sorted(families, key=str.lower):
                yield families[family]


metrics = PrometheusMetrics()
