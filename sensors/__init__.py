from sensors.sensor import Gauge, Counter, Switch, Message
from sensors.sensor import SENSOR, ACTUATOR, GAUGE, COUNTER, SWITCH, MESSAGE
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
import json
import logging

# create logger
logger = logging.getLogger('switchboard.sensors')


class Sensors():
    '''container to store sensors'''

    def __init__(self):
        self.node_id_index = {}
        self.sensor_index = []
        self.sio = None

    def __add_sensor(self,
                     source,
                     node_id,
                     node_addr,
                     sensor_id,
                     sensor_config_dict,
                     mode=SENSOR):

        param = {
            'source': source,
            'node_id': node_id,
            'node_addr': node_addr,
            'sensor_id': sensor_id,
            'mode': mode
        }

        for p in [
                'default_value', 'accept_refresh', 'ttl', 'hidden',
                'eval_preserve', 'eval_expr', 'eval_require', 'dataset', 'key'
        ]:
            if p in sensor_config_dict:
                param[p] = sensor_config_dict[p]

        if 'type' in sensor_config_dict:
            type = sensor_config_dict['type']
        else:
            type = 'gauge'

        m = {
            'gauge': Gauge(**param),
            'counter': Counter(**param),
            'switch': Switch(**param),
            'message': Message(**param)
        }

        sensor = m[type]

        self.sensor_index.append(sensor)
        self.node_id_index[node_id][sensor_id] = sensor

    def __add_node(self, node_id, source, node_config_dict):
        '''set up node and its sensors'''

        if 'addr' in node_config_dict:
            node_addr = node_config_dict['addr']
        else:
            node_addr = None

        if not node_id in self.node_id_index:
            self.node_id_index[node_id] = {}

        if 'sensors' in node_config_dict:
            for sensor_id, sensor_config_dict in node_config_dict[
                    'sensors'].items():
                self.__add_sensor(
                    source,
                    node_id,
                    node_addr,
                    sensor_id,
                    sensor_config_dict,
                    mode=SENSOR)

        if 'actuators' in node_config_dict:
            for sensor_id, sensor_config_dict in node_config_dict[
                    'actuators'].items():
                self.__add_sensor(
                    source,
                    node_id,
                    node_addr,
                    sensor_id,
                    sensor_config_dict,
                    mode=ACTUATOR)

    def __add_source(self, source, source_config_dict):
        for node_id, node_config_dict in source_config_dict.items():
            self.__add_node(node_id, source, node_config_dict)

    def add_sensors(self, config_dict):
        for source, source_config_dict in config_dict.items():
            self.__add_source(source, source_config_dict)

        self.prev_data = self.get_sensors_dict_by_node(skip_None=False)

    def __get_sensor(self, node_id, sensor_id):
        return self.node_id_index[node_id][sensor_id]

    def get_sensors_dump(self):
        for sensor in self.sensor_index:
            yield dict(sensor.get_data())

    def get_sensors_dump_list(self):
        return list(self.get_sensors_dump())

    def get_sensors_dump_dict(self):
        ret = {}
        for sensor in self.sensor_index:
            if not sensor.source in ret:
                ret[sensor.source] = {}

            if not sensor.node_id in ret[sensor.source]:
                ret[sensor.source][sensor.node_id] = {}

            ret[sensor.source][sensor.node_id][sensor.sensor_id] = dict(
                sensor.get_data())
        return ret

    def get_sensors_addr_config(self, source):
        config_keys = {'sensor_id', 'node_id', 'mode', 'node_addr', 'key'}
        for sensor in self.sensor_index:
            if sensor.source == source:
                yield dict(
                    sensor.get_data(skip_None=True, selected=config_keys))

    def get_sensors_data(self, skip_None=True):
        state_metrics = {
            'value', 'hits_total', 'hit_timestamp', 'duration_seconds'
        }
        for node_id in self.node_id_index:
            for sensor_id, sensor in self.node_id_index[node_id].items():
                yield node_id, sensor_id, dict(
                    sensor.get_data(
                        skip_None=skip_None, selected=state_metrics))

    def get_sensors_dict_by_node(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_sensors_data(
                skip_None=skip_None):
            if not node_id in ret:
                ret[node_id] = {}
            if not sensor_id in ret[node_id]:
                ret[node_id][sensor_id] = data
        return ret

    def get_sensors_dict_by_sensor(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_sensors_data(
                skip_None=skip_None):
            if not sensor_id in ret:
                ret[sensor_id] = {}
            if not node_id in ret[sensor_id]:
                ret[sensor_id][node_id] = data
        return ret

    def __get_changed_nodes_dict(self, first={}, second={}, level=0):
        changed = {}

        if level == 0:
            first = self.prev_data
            second = self.get_sensors_dict_by_node(skip_None=False)

        for key in first:
            if (first[key] != second[key]):  #changed
                if level < 2:
                    changed[key] = self.__get_changed_nodes_dict(
                        first=first[key], second=second[key], level=level + 1)
                else:
                    changed[key] = second[key]

        for key in second:
            if (not key in first):  #added
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
                        logger.error('{}.{}: error in eval_require {}'.format(
                            node_id, sensor_id, sensor.eval_require))
                        return {}

                    sensor = self.__get_sensor(node_id, sensor_id)
                    value = next(sensor.get_data(selected={metric_name}))[1]

                    if sensor.dataset and not sensor.dataset_ready:
                        value = None

                    if value is not None:
                        ret[var] = value
                        used_list.append(self.__get_sensor(node_id, sensor_id))
                    else:
                        return {}
            except:
                return {}

        for s in used_list:
            s.dataset_use()

        return ret

    def __get_requiring_sensors(self, sensor):
        x = set()

        for s in self.sensor_index:
            if s.eval_require is not None:
                for var, metric_list in s.eval_require.items():
                    if len(metric_list) == 3:
                        (node_id, sensor_id, metric_name) = tuple(metric_list)
                    elif len(metric_list) == 2:
                        (sensor_id, metric_name) = tuple(metric_list)
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

        if diff and self.sio is not None:
            for node_id in diff:
                logger.info('complete sensor changes: {}'.format({
                    node_id:
                    diff[node_id]
                }))
                self.sio.emit(
                    'event',
                    json.dumps({
                        node_id: diff[node_id]
                    }),
                    broadcast=True,
                    namespace='/events')
                for sensor_id, metrics in diff[node_id].items():
                    sensor = self.__get_sensor(node_id, sensor_id)
                    for metric in metrics:
                        if sensor.mode == ACTUATOR and metric == 'value':
                            logger.debug(
                                'emit actuator event: {}.{}: {}'.format(
                                    node_id, sensor_id, sensor.value))
                            self.sio.emit(
                                'actuator_response',
                                json.dumps({
                                    node_id: {
                                        sensor_id: sensor.value
                                    }
                                }),
                                room=sensor.source,
                                namespace='/sensors')

    def set_values(self, node_id, sensor_values_dict):
        changed = 0

        for sensor_id in sensor_values_dict:
            sensor = self.__get_sensor(node_id, sensor_id)
            if sensor.set(sensor_values_dict[sensor_id]):
                changed = 1

                if sensor.eval_expr is not None:
                    vars_dict = self.__get_sensor_required_vars_dict(sensor)
                    sensor.do_eval(
                        vars_dict=vars_dict,
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
            if sensor.dec_ttl():
                changed = 1
                logger.debug("scheduler: {}.{} ttl timed out".format(
                    sensor.node_id, sensor.sensor_id))
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
            EXPORTER_NAME = "switchboard"

            d = {}
            for sensor in self.sensors.sensor_index:
                if sensor.hidden:
                    continue

                for name, metric_type, value, labels, labels_data in sensor.get_promexport_data(
                ):
                    if not name in d:
                        metric_name = "{}_{}".format(EXPORTER_NAME, name)
                        if metric_type == COUNTER:
                            x = CounterMetricFamily(
                                metric_name, '', labels=labels)
                        else:
                            x = GaugeMetricFamily(
                                metric_name, '', labels=labels)
                        d[name] = x
                    else:
                        x = d[name]

                    x.add_metric(labels_data, value)

            for q in d:
                yield d[q]
