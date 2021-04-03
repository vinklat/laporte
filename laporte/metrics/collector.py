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
from ..core.sensor import COUNTER
from ..version import app_name, __version__
from ..metrics import metrics
from ..core import sensors

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/metrics')
def export_metrics():
    '''Export prometheus metrics'''
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


class CustomCollector():
    def __init__(self, inner_metrics, inner_sensors):
        self.metrics = inner_metrics
        self.sensors = inner_sensors

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
                labels = values_data['labels']

                if metric_id not in families:
                    label_keys = list(map(itemgetter(0), labels.items()))
                    help_str = '{} (labels: {})'.format(
                        values_data['help_str'],
                        ', '.join(label_keys)) if label_keys else values_data['help_str']
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
                        values_data['help_str'],
                        ', '.join(label_keys)) if label_keys else values_data['help_str']
                    met = CounterMetricFamily(metric_id.split('[')[0],
                                              help_str,
                                              labels=label_keys)
                    families[metric_id] = met
                else:
                    met = families[metric_id]

                label_values = list(map(itemgetter(1), labels.items()))
                met.add_metric(label_values, total)

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


REGISTRY.register(CustomCollector(metrics, sensors))
