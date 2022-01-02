# -*- coding: utf-8 -*-
'''
Metrics Blueprint with custom collector
'''

from operator import itemgetter
from flask import Blueprint, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import REGISTRY
from prometheus_client.core import (InfoMetricFamily, GaugeMetricFamily,
                                    CounterMetricFamily, SummaryMetricFamily)
from laporte.core.sensor import COUNTER
from laporte.version import app_name, __version__
from laporte.metrics import metrics
from laporte.core import sensors

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/metrics')
def export_metrics():
    '''Export prometheus metrics'''
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


class CustomCollector():
    def __init__(self, inner_metrics, inner_sensors):
        self.metrics = inner_metrics
        self.sensors = inner_sensors

    def __get_label_keys(self, values_data: dict) -> list:
        '''
        get keys (names) of all labels
        '''

        if 'labels' not in values_data:
            return []

        labels = values_data['labels']
        return list(map(itemgetter(0), labels.items()))

    def __get_label_values(self, values_data: dict) -> list:
        '''
        get values of all labels
        '''

        if 'labels' not in values_data:
            return []

        labels = values_data['labels']
        return list(map(itemgetter(1), labels.items()))

    def __get_help_str(self, values_data: dict) -> str:
        '''
        generate string of help message
        '''

        label_keys = self.__get_label_keys(values_data)
        if label_keys:
            labels_str = ', '.join(label_keys)
            help_str = f"{values_data['help_str']} (labels: {labels_str})"
        else:
            help_str = values_data['help_str']

        return help_str

    def collect(self):

        # version info
        families = {
            "0":
            InfoMetricFamily(app_name,
                             f'{app_name} version',
                             value={'version': __version__})
        }

        # dump stored durations
        for metric_id, labels_data in self.metrics.summaries.items():
            for _, values_data in labels_data.items():  # unused values_key
                count = values_data['count']
                summ = values_data['sum']

                if metric_id not in families:
                    met = SummaryMetricFamily(metric_id.split('[')[0],
                                              self.__get_help_str(values_data),
                                              labels=self.__get_label_keys(values_data))
                    families[metric_id] = met
                else:
                    met = families[metric_id]

                met.add_metric(self.__get_label_values(values_data), count, summ)

        # dump stored counters
        for metric_id, labels_data in self.metrics.counters.items():
            for _, values_data in labels_data.items():  # unused values_key
                total = values_data['total']

                if metric_id not in families:
                    met = CounterMetricFamily(metric_id.split('[')[0],
                                              self.__get_help_str(values_data),
                                              labels=self.__get_label_keys(values_data))
                    families[metric_id] = met
                else:
                    met = families[metric_id]

                met.add_metric(self.__get_label_values(values_data), total)

        for family in sorted(families, key=str.lower):
            yield families[family]

        # dump laporte sensors
        for sensor in self.sensors.sensor_index:
            if sensor.export_hidden:
                continue

            for (name, metric_type, value, labels, labels_data,
                 prefix) in sensor.get_promexport_data():
                if prefix is None:
                    metric_name = f'{app_name}_{name}'
                else:
                    metric_name = f'{prefix}_{name}' if prefix else name

                uniqname = f'{metric_name}_' + '_'.join(labels)
                if uniqname not in families:
                    help_str = f"with labels: {labels}"
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


REGISTRY.register(CustomCollector(metrics, sensors))
