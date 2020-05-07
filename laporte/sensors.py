# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring, missing-class-docstring
'''objects that collect sets of sensors'''

import json
import logging
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateNotFound
from yaml import safe_load, YAMLError
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, InfoMetricFamily
from laporte.version import __version__
from laporte.sensor import Gauge, Counter, Binary, Message
from laporte.sensor import SENSOR, ACTUATOR, GAUGE, COUNTER, BINARY

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

METRICS_NAMESPACE = '/metrics'
EVENTS_NAMESPACE = '/events'

METRICS = {'value', 'hits_total', 'hit_timestamp', 'duration_seconds'}
SETUP = {'sensor_id', 'node_id', 'mode', 'node_addr', 'key'}


class Sensors():
    '''container to store a set of sensors'''
    def reset(self):
        self.node_id_index = {}
        self.node_template_index = {}
        self.sensor_template_index = {}
        self.sensor_index = []

    def __init__(self):
        self.reset()
        self.sio = None
        self.prev_data = {}

    def __add_sensor(self,
                     gw,
                     node_id,
                     node_addr,
                     sensor_id,
                     sensor_config_dict,
                     sensor_parent_config_dict,
                     template=False,
                     mode=SENSOR):

        param = {
            'gw': gw,
            'node_id': node_id,
            'node_addr': node_addr,
            'sensor_id': sensor_id,
            'mode': mode
        }

        for p in [
                'default_value', 'debounce', 'ttl', 'eval_preserve',
                'eval_expr', 'eval_require', 'reserved', 'key'
        ]:
            if p in sensor_parent_config_dict:
                #note: only ttl should pass now
                param[p] = sensor_parent_config_dict[p]

            if p in sensor_config_dict:
                param[p] = sensor_config_dict[p]

        for p in ['export']:  #only export at this time
            if p in sensor_parent_config_dict:
                param['parent_' + p] = sensor_parent_config_dict[p]

            if p in sensor_config_dict:
                param[p] = sensor_config_dict[p]

        if 'type' in sensor_config_dict:
            t = sensor_config_dict['type']
        else:
            t = 'gauge'

        if t == 'message':
            sensor = Message(**param)
        elif t == 'counter':
            sensor = Counter(**param)
        elif t == 'binary':
            sensor = Binary(**param)
        else:
            sensor = Gauge(**param)

        if not template:
            self.sensor_index.append(sensor)
            self.node_id_index[node_id][sensor_id] = sensor
        else:
            self.node_template_index[node_id][sensor_id] = sensor
            self.sensor_template_index[sensor_id] = node_id

    def __add_node(self, node_id, gw, node_config_dict, template=False):
        '''set up node and its sensors'''

        if 'addr' in node_config_dict and not template:
            node_addr = node_config_dict['addr']
        else:
            node_addr = None

        if not template:
            if node_id not in self.node_id_index:
                self.node_id_index[node_id] = {}
        else:
            if node_id not in self.node_template_index:
                self.node_template_index[node_id] = {}

        sensor_parent_config_dict = {}

        for key in ['export', 'ttl']:
            if key in node_config_dict:
                sensor_parent_config_dict[key] = node_config_dict[key]

        for key, mode in {'sensors': SENSOR, 'actuators': ACTUATOR}.items():
            if key in node_config_dict:
                for sensor_id, sensor_config_dict in node_config_dict[
                        key].items():
                    self.__add_sensor(gw,
                                      node_id,
                                      node_addr,
                                      sensor_id,
                                      sensor_config_dict,
                                      sensor_parent_config_dict,
                                      template=template,
                                      mode=mode)

    def __add_gw(self, gw, gw_config_dict):
        for node_id, node_config_dict in gw_config_dict.items():
            if isinstance(node_id, int):
                self.__add_node(node_id, gw, node_config_dict, template=True)
            else:
                self.__add_node(node_id, gw, node_config_dict)

    def add_sensors(self, config_dict):
        for gw, gw_config_dict in config_dict.items():
            self.__add_gw(gw, gw_config_dict)
        self.prev_data = {}

    def __get_sensor(self, node_id, sensor_id):
        return self.node_id_index[node_id][sensor_id]

    def __find_addr(self, node_addr, key):
        '''return a sensor with given node_addr and key'''

        for sensor in self.sensor_index:
            if (sensor.node_addr == node_addr) and (sensor.key == key):
                return sensor
        return None

    def get_metrics_of_sensor(self, node_id, sensor_id):
        sensor = self.__get_sensor(node_id, sensor_id)
        return sensor.get_data(skip_None=False, selected=METRICS)

    def get_metrics_of_node(self, node_id):
        for sensor_id, sensor in self.node_id_index[node_id].items():
            yield sensor_id, dict(
                sensor.get_data(skip_None=False, selected=METRICS))

    def get_metrics(self, skip_None=True):
        for node_id in self.node_id_index:
            for sensor_id, sensor in self.node_id_index[node_id].items():
                yield node_id, sensor_id, dict(
                    sensor.get_data(skip_None=skip_None, selected=METRICS))

    def get_metrics_dict_by_gw(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_metrics(skip_None=skip_None):
            gw = self.__get_sensor(node_id, sensor_id).gw
            if not gw in ret:
                ret[gw] = {}
            if not node_id in ret[gw]:
                ret[gw][node_id] = {}
            if not sensor_id in ret[gw][node_id]:
                ret[gw][node_id][sensor_id] = data
        return ret

    def get_metrics_dict_by_node(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_metrics(skip_None=skip_None):
            if not node_id in ret:
                ret[node_id] = {}
            if not sensor_id in ret[node_id]:
                ret[node_id][sensor_id] = data
        return ret

    def get_metrics_dict_by_sensor(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_metrics(skip_None=skip_None):
            if not sensor_id in ret:
                ret[sensor_id] = {}
            if not node_id in ret[sensor_id]:
                ret[sensor_id][node_id] = data
        return ret

    def get_sensors_dump_dict(self):
        ret = {}
        for sensor in self.sensor_index:
            if not sensor.gw in ret:
                ret[sensor.gw] = {}

            if not sensor.node_id in ret[sensor.gw]:
                ret[sensor.gw][sensor.node_id] = {}

            ret[sensor.gw][sensor.node_id][sensor.sensor_id] = dict(
                sensor.get_data())
        return ret

    def get_config_of_gw(self, gw):
        for sensor in self.sensor_index:
            if sensor.gw == gw:
                yield dict(sensor.get_data(skip_None=True, selected=SETUP))

    def __get_changed_nodes_dict(self, first=None, second=None, level=0):
        changed = {}

        # because {} is dangerous default value
        if first is None:
            first = {}
        if second is None:
            second = {}

        if level == 0:
            first = self.prev_data
            second = self.get_metrics_dict_by_node(skip_None=False)

        for key in first:
            if first[key] != second[key]:  #changed
                if level < 2:
                    changed[key] = self.__get_changed_nodes_dict(
                        first=first[key], second=second[key], level=level + 1)
                else:
                    changed[key] = second[key]

        for key in second:
            if not key in first:  #added
                if level < 2:
                    changed[key] = self.__get_changed_nodes_dict(
                        second=second[key], level=level + 1)
                else:
                    changed[key] = second[key]

        if level == 0:
            self.prev_data = second

        return changed

    def __get_sensor_required_vars_dict(self, sensor):
        ret = {}
        used_list = []

        if sensor.eval_require is not None:
            try:
                for var, metric_list in sensor.eval_require.items():
                    if len(metric_list) == 3:
                        (node_id, sensor_id, metric_name) = tuple(metric_list)
                    elif len(metric_list) == 2:
                        (sensor_id, metric_name) = tuple(metric_list)
                        node_id = sensor.node_id
                    else:
                        logging.error("%s.%s: error in eval_require %s",
                                      node_id, sensor_id, sensor.eval_require)
                        return {}

                    search_sensor = self.__get_sensor(node_id, sensor_id)
                    value = next(
                        search_sensor.get_data(selected={metric_name}))[1]

                    if search_sensor.debounce_dataset and not search_sensor.dataset_ready:
                        value = None

                    if value is not None:
                        ret[var] = value
                        used_list.append(self.__get_sensor(node_id, sensor_id))
                    else:
                        return {}
            except KeyError:
                logging.debug(
                    "skip eval %s.%s: required sensor %s.%s not found",
                    sensor.node_id, sensor.sensor_id, node_id, sensor_id)
                return {}
            except StopIteration:
                logging.debug(
                    "skip eval %s.%s: required metric %s of %s.%s not found",
                    sensor.node_id, sensor.sensor_id, metric_name, node_id,
                    sensor_id)
                return {}

        for s in used_list:
            s.dataset_use()

        return ret

    def __get_requiring_sensors(self, sensor):
        x = set()

        for s in self.sensor_index:
            if s.eval_require is not None:
                for _, metric_list in s.eval_require.items():
                    if len(metric_list) == 3:
                        (node_id, sensor_id,
                         _) = tuple(metric_list)  # unused metric_name
                    elif len(metric_list) == 2:
                        (sensor_id,
                         _) = tuple(metric_list)  # unused metric_name
                        node_id = s.node_id

                    if node_id == sensor.node_id and sensor_id == sensor.sensor_id and not s in x:
                        x.add(s)
                        yield s

    def __do_requiring_eval(self, sensor, level=0):
        if level < 8:
            for s in self.__get_requiring_sensors(sensor):
                vars_dict = self.__get_sensor_required_vars_dict(s)
                if s.do_eval(vars_dict=vars_dict):
                    self.__do_requiring_eval(s, level=level + 1)

    def __used_dataset_reset(self):
        for s in self.sensor_index:
            if s.dataset_used:
                s.dataset_reset()

    def emit_changes(self, diff):
        ''' emit sensor data of chaged nodes to SocketIO event log namespace'''

        actuator_id_values = {}
        actuator_addr_values = {}

        if diff and self.sio is not None:
            for node_id in diff:
                logging.info('complete sensor changes: %s',
                             {node_id: diff[node_id]})
                self.sio.emit('update_response',
                              json.dumps({node_id: diff[node_id]}),
                              namespace=EVENTS_NAMESPACE)

                for sensor_id, metrics in diff[node_id].items():
                    sensor = self.__get_sensor(node_id, sensor_id)
                    for metric in metrics:
                        if sensor.mode == ACTUATOR and metric == 'value':
                            if sensor.gw not in actuator_id_values:
                                actuator_id_values[sensor.gw] = {}
                            if node_id not in actuator_id_values[sensor.gw]:
                                actuator_id_values[sensor.gw][node_id] = {}
                            actuator_id_values[
                                sensor.gw][node_id][sensor_id] = sensor.value
                            if (sensor.node_addr != '') and (sensor.key != ''):
                                if sensor.gw not in actuator_addr_values:
                                    actuator_addr_values[sensor.gw] = {}
                                if sensor.node_addr not in actuator_addr_values[
                                        sensor.gw]:
                                    actuator_addr_values[sensor.gw][
                                        sensor.node_addr] = {}
                                actuator_addr_values[sensor.gw][
                                    sensor.node_addr][
                                        sensor.key] = sensor.value

        if actuator_id_values:
            for gateway, data in actuator_id_values.items():
                logging.info('changed actuator ids: %s', data)
                self.sio.emit('actuator_response',
                              json.dumps({gateway: data}),
                              room=gateway,
                              namespace=METRICS_NAMESPACE)

        if actuator_addr_values:
            for gateway, data in actuator_addr_values.items():
                logging.info('changed actuator addrs: %s', data)
                self.sio.emit('actuator_addr_response',
                              json.dumps({gateway: data}),
                              room=gateway,
                              namespace=METRICS_NAMESPACE)

    def conv_addrs_to_ids(self, addrs_dict):
        '''
        convert {node_addr:{key:value}} dict
        to
        {node_id:{sensor_id:value}} dict
        '''

        ret = {}
        for node_addr, key_values_dict in addrs_dict.items():
            for key, value in key_values_dict.items():

                sensor = self.__find_addr(node_addr, key)
                if sensor is not None:
                    if sensor.node_id not in ret:
                        ret[sensor.node_id] = {}
                    ret[sensor.node_id][sensor.sensor_id] = value
                else:
                    logging.warning("sensor %s:%s not found in node",
                                    node_addr, key)
        return ret

    def set_values(self, node_id, sensor_values_dict, increment=False):
        changed = 0

        for sensor_id in sensor_values_dict:

            # create new node if there is a template
            if (not node_id in self.node_id_index) and (
                    sensor_id in self.sensor_template_index):
                logging.debug("setup new node %s from template.", node_id)
                self.node_id_index[node_id] = {}
                t = self.sensor_template_index[sensor_id]
                for sx_id, sx in self.node_template_index[t].items():
                    sensor = sx.clone(node_id)
                    self.node_id_index[node_id][sx_id] = sensor
                    self.sensor_index.append(sensor)

            sensor = self.__get_sensor(node_id, sensor_id)
            if sensor.set(sensor_values_dict[sensor_id], increment=increment):
                changed = 1

                if sensor.eval_expr is not None:
                    vars_dict = self.__get_sensor_required_vars_dict(sensor)
                    sensor.do_eval(vars_dict=vars_dict,
                                   update=False,
                                   preserve_override=True)

                self.__do_requiring_eval(sensor)
                self.__used_dataset_reset()

        changes = {}
        if changed:
            changes = self.__get_changed_nodes_dict()
            self.emit_changes(changes)

        return changes

    def update_sensors_ttl(self, interval=1):
        '''decrease remaining active ttls for sensors of all nodes (called from scheduller)'''

        changed = 0

        for sensor in self.sensor_index:
            if sensor.dec_ttl(interval):
                changed = 1
                logging.debug("scheduler: %s.%s ttl timed out", sensor.node_id,
                              sensor.sensor_id)
                self.__do_requiring_eval(sensor)
                self.__used_dataset_reset()

        changes = {}
        if changed:
            changes = self.__get_changed_nodes_dict()
            self.emit_changes(changes)

    class CustomCollector(object):
        def __init__(self, inner_sensors):
            self.sensors = inner_sensors

        def collect(self):
            EXPORTER_NAME = 'laporte'

            # add laporte versison at first
            d = {
                "0":
                InfoMetricFamily(EXPORTER_NAME,
                                 'help',
                                 value={'version': __version__})
            }

            for sensor in self.sensors.sensor_index:
                if sensor.export_hidden:
                    continue

                for (name, metric_type, value, labels, labels_data,
                     prefix) in sensor.get_promexport_data():
                    uniqname = name + '_' + '_'.join(labels)
                    if not uniqname in d:
                        if prefix is None:
                            metric_name = '{}_{}'.format(EXPORTER_NAME, name)
                        elif prefix == "":
                            metric_name = name
                        else:
                            metric_name = '{}_{}'.format(prefix, name)

                        if metric_type == COUNTER:
                            x = CounterMetricFamily(metric_name,
                                                    'with labels: ' +
                                                    ', '.join(labels),
                                                    labels=labels)
                        else:
                            x = GaugeMetricFamily(metric_name,
                                                  'with labels: ' +
                                                  ', '.join(labels),
                                                  labels=labels)
                        d[uniqname] = x
                    else:
                        x = d[uniqname]

                    x.add_metric(labels_data, value)

            for q in sorted(d, key=str.lower):
                yield d[q]

    def get_parser_arguments(self):

        d = {}
        for sensor in self.sensor_index:
            t = sensor.get_type()

            if t == GAUGE or t == COUNTER:
                d[sensor.sensor_id] = (float, 'decimal')
            elif t == BINARY:
                d[sensor.sensor_id] = (bool, 'boolean')
            else:
                d[sensor.sensor_id] = (str, 'string')

        for q in d:
            yield q, d[q][0], d[q][1]

    def default_values(self):
        for sensor in self.sensor_index:
            sensor.reset()

        changes = self.__get_changed_nodes_dict()
        self.emit_changes(changes)

        return changes

    def reset_values(self):
        for sensor in self.sensor_index:
            sensor.__init__()

        changes = self.__get_changed_nodes_dict()
        self.emit_changes(changes)

        return changes

    def load_config(self, pars):
        try:
            with open(pars.sensors_fname, 'r') as stream:
                if pars.jinja2:
                    # load jinja2
                    t = Environment(
                        loader=FileSystemLoader(pars.sensors_dir)).from_string(
                            stream.read())
                    # load yaml
                    config_dict = safe_load(t.render())
                else:
                    # load yaml
                    config_dict = safe_load(stream)
        except (YAMLError, TemplateSyntaxError, TemplateNotFound,
                FileNotFoundError) as exc:
            logging.error("Cant't read config: %s", exc)
            exit(1)

        self.add_sensors(config_dict)
        changes = self.__get_changed_nodes_dict()
        return changes

    def reload_config(self, pars):
        self.default_values()
        self.reset()
        changes = self.load_config(pars)
        self.emit_changes(changes)
        self.sio.emit('reload_response')
        return changes
