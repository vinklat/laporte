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
        self.sensor_addr_index = {}
        self.node_id_index = {}
        self.source_index = {}
        self.sensor_index = []

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
            'sensor_id': sensor_id,
            'mode': mode
        }

        for p in [
                'default_value', 'accept_refresh', 'ttl', 'hidden',
                'eval_preserve', 'eval_expr', 'eval_require', 'dataset'
        ]:
            if p in sensor_config_dict:
                param[p] = sensor_config_dict[p]

        if 'key' in sensor_config_dict and not node_addr is None:
            sensor_addr = '{}/{}'.format(node_addr, sensor_config_dict['key'])
            param['addr'] = sensor_addr
        else:
            sensor_addr = None

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
        if sensor_addr is not None:
            self.sensor_addr_index[sensor_addr] = sensor
            self.source_index[source][sensor_addr] = sensor

    def __add_node(self, node_id, source, node_config_dict):
        '''set up node and its sensors'''

        if 'addr' in node_config_dict:
            node_addr = node_config_dict['addr']
        else:
            node_addr = None

        if not node_id in self.node_id_index:
            self.node_id_index[node_id] = {}

        nsensors = 0
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
                nsensors + -1

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
                nsensors + -1

        if not nsensors:
            return 0

    def __add_source(self, source, source_config_dict):
        if not source in self.source_index:
            self.source_index[source] = {}

        for node_id, node_config_dict in source_config_dict.items():
            self.__add_node(node_id, source, node_config_dict)

    def add_sensors(self, config_dict):
        for source, source_config_dict in config_dict.items():
            self.__add_source(source, source_config_dict)

        self.prev_data = self.get_sensors_dict_by_node(skip_None=False)

    def get_sensor_metric(self, node_id, sensor_id, metric):
        v = next(self.node_id_index[node_id][sensor_id].get_data(
            selected={metric}))[1]
        return v

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
        config_keys = {'sensor_id', 'node_id', 'mode'}
        for sensor_addr, sensor in self.source_index[source].items():
            yield sensor_addr, dict(
                sensor.get_data(skip_None=True, selected=config_keys))

    def get_sensors_data(self, skip_None=True):
        state_metrics = {
            'value', 'hits_total', 'hit_timestamp', 'interval_seconds'
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

        if sensor.eval_require is not None:
            try:
                for var, nodes in sensor.eval_require.items():
                    for node_id, sensors in nodes.items():
                        for sensor_id, metric_name in sensors.items():
                            value = self.get_sensor_metric(
                                node_id, sensor_id, metric_name)
                            if value is not None:
                                ret[var] = value
                            else:
                                return {}
            except:
                return {}
        return ret

    def __get_requiring_sensors(self, sensor):
        x = set()

        for s in self.sensor_index:
            if s.eval_require is not None:
                for var, requires in s.eval_require.items():
                    for node_id, sensors in requires.items():
                        if node_id == sensor.node_id:
                            for sensor_id in sensors:
                                if sensor_id == sensor.sensor_id and not s in x:
                                    x.add(s)
                                    yield s

    def __do_requiring_eval(self, sensor, level=0):
        if level < 8:
            for s in self.__get_requiring_sensors(sensor):
                vars_dict = self.__get_sensor_required_vars_dict(s)
                if s.do_eval(vars_dict=vars_dict):
                    self.__do_requiring_eval(s, level=level + 1)

    sio = None

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
                    namespace='/log')
                for sensor_id, metrics in diff[node_id].items():
                    sensor = self.node_id_index[node_id][sensor_id]
                    for metric in metrics:
                        if sensor.mode == ACTUATOR and metric == 'value':
                            logger.debug(
                                'emit actuator event: {}.{}: {}'.format(
                                    node_id, sensor_id, sensor.value))
                            self.sio.emit('actuator_response',
                                          json.dumps(
                                              {
                                                  node_id: {
                                                      sensor_id: sensor.value
                                                  }
                                              },
                                              room=sensor.source,
                                              namespace='/sensors'))

    def set_values(self, node_id, sensor_values_dict):
        changed = 0

        for sensor_id in sensor_values_dict:
            sensor = self.node_id_index[node_id][sensor_id]
            if sensor.set(sensor_values_dict[sensor_id]):
                changed = 1

                if sensor.eval_expr is not None:
                    vars_dict = self.__get_sensor_required_vars_dict(sensor)
                    sensor.do_eval(
                        vars_dict=vars_dict,
                        update=False,
                        preserve_override=True)

                self.__do_requiring_eval(sensor)

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
