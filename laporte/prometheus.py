# -*- coding: utf-8 -*-
'''
objects for Prometheus metrics
'''

import logging
from operator import itemgetter
from time import time
from functools import wraps
from prometheus_client.core import (InfoMetricFamily, GaugeMetricFamily,
                                    CounterMetricFamily, SummaryMetricFamily)
from laporte.sensor import COUNTER
from laporte.version import __version__

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

EXPORTER_NAME = 'laporte'


class PrometheusMetrics:
    durations = {}
    counters = {}

    def __init__(self, sensors):
        self.sensors = sensors

    def func_measure(self, labels):
        '''
        update duration (summary) of any function with this decorator is called
        '''
        def decorator(func):
            @wraps(func)
            def _time_it(*args, **kwargs):
                start_t = time()
                try:
                    return func(*args, **kwargs)
                finally:
                    labels_key = 'duration_' + str(
                        list(map(itemgetter(0), labels.items())))
                    values_key = str(list(map(itemgetter(1), labels.items())))

                    if labels_key not in self.durations:
                        self.durations[labels_key] = {}
                    if values_key not in self.durations[labels_key]:
                        self.durations[labels_key][values_key] = {
                            'count': 0,
                            'sum': 0.0,
                            'labels': labels
                        }

                    duration = time() - start_t
                    logging.debug("duration: %fs", duration)

                    self.durations[labels_key][values_key]['count'] += 1
                    self.durations[labels_key][values_key]['sum'] += duration

            return _time_it

        return decorator

    def func_count(self, labels):
        '''update number of times any function with this decorator is called'''
        def decorator(func):
            @wraps(func)
            def _inc_count(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                finally:
                    self.counter_inc(labels)

            return _inc_count

        return decorator

    def counter_inc(self, labels):
        '''update counter'''
        labels_key = 'counts_' + str(list(map(itemgetter(0), labels.items())))
        values_key = str(list(map(itemgetter(1), labels.items())))

        if labels_key not in self.counters:
            self.counters[labels_key] = {}
        if values_key not in self.counters[labels_key]:
            self.counters[labels_key][values_key] = {'total': 0, 'labels': labels}

        self.counters[labels_key][values_key]['total'] += 1

    class CustomCollector():
        def __init__(self, inner_metrics):
            self.metrics = inner_metrics

        def collect(self):

            # laporte version info
            families = {
                "0":
                InfoMetricFamily(EXPORTER_NAME,
                                 'Laporte version',
                                 value={'version': __version__})
            }

            # dump stored durations
            for labels_key, labels_data in self.metrics.durations.items():
                for _, values_data in labels_data.items():  # unused values_key
                    count = values_data['count']
                    summ = values_data['sum']
                    labels = values_data['labels']

                    if labels_key not in families:
                        label_keys = list(map(itemgetter(0), labels.items()))

                        met = SummaryMetricFamily(EXPORTER_NAME + '_duration_seconds',
                                                  'counter and duration of runs of '
                                                  'function with labels ' +
                                                  str(label_keys),
                                                  labels=label_keys)
                        families[labels_key] = met
                    else:
                        met = families[labels_key]

                    label_values = list(map(itemgetter(1), labels.items()))
                    met.add_metric(label_values, count, summ)

            # dump stored counters
            for labels_key, labels_data in self.metrics.counters.items():
                for _, values_data in labels_data.items():  # unused values_key
                    total = values_data['total']
                    labels = values_data['labels']

                    if labels_key not in families:
                        label_keys = list(map(itemgetter(0), labels.items()))

                        met = CounterMetricFamily(EXPORTER_NAME + '_count_total',
                                                  'counter of something with labels ' +
                                                  str(label_keys),
                                                  labels=label_keys)
                        families[labels_key] = met
                    else:
                        met = families[labels_key]

                    label_values = list(map(itemgetter(1), labels.items()))
                    met.add_metric(label_values, total)

            # dump laporte sensors
            for sensor in self.metrics.sensors.sensor_index:
                if sensor.export_hidden:
                    continue

                for (name, metric_type, value, labels, labels_data,
                     prefix) in sensor.get_promexport_data():
                    uniqname = name + '_' + '_'.join(labels)
                    if uniqname not in families:
                        if prefix is None:
                            metric_name = '{}_{}'.format(EXPORTER_NAME, name)
                        elif prefix == "":
                            metric_name = name
                        else:
                            metric_name = '{}_{}'.format(prefix, name)

                        if metric_type == COUNTER:
                            x = CounterMetricFamily(metric_name,
                                                    'with labels: ' + ', '.join(labels),
                                                    labels=labels)
                        else:
                            x = GaugeMetricFamily(metric_name,
                                                  'with labels: ' + ', '.join(labels),
                                                  labels=labels)
                        families[uniqname] = x
                    else:
                        x = families[uniqname]

                    x.add_metric(labels_data, value)

            for family in sorted(families, key=str.lower):
                yield families[family]
