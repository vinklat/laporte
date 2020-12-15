# -*- coding: utf-8 -*-
'''objects that collect sets of sensors'''

import logging
import json
from datetime import datetime, timedelta
from jinja2 import (Environment, FileSystemLoader, TemplateSyntaxError, TemplateNotFound)
from yaml import safe_load, YAMLError
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from laporte.version import __version__
from laporte.sensor import Gauge, Counter, Binary, Message
from laporte.sensor import SENSOR, ACTUATOR, GAUGE, COUNTER, BINARY

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

METRICS_NAMESPACE = '/metrics'
EVENTS_NAMESPACE = '/events'

METRICS = {
    'value', 'hits_total', 'hit_timestamp', 'duration_seconds', 'ttl_job', 'cron_jobs'
}
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
        self.scheduler = None
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

        for p in ['default', 'debounce', 'ttl', 'eval', 'group', 'desc', 'cron', 'key']:
            if p in sensor_parent_config_dict:
                # note: only ttl should pass now
                param[p] = sensor_parent_config_dict[p]

            if p in sensor_config_dict:
                param[p] = sensor_config_dict[p]

        for p in ['export']:  # only export at this time
            if p in sensor_parent_config_dict:
                param['parent_' + p] = sensor_parent_config_dict[p]

            if p in sensor_config_dict:
                param[p] = sensor_config_dict[p]

        # rename eval because it's Python built-in
        if 'eval' in param:
            param['pyeval'] = param['eval']
            del param['eval']

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
            self.__add_cron_jobs(sensor)
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
                for sensor_id, sensor_config_dict in node_config_dict[key].items():
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

    def __add_cron_jobs(self, sensor):
        if isinstance(sensor.cron, dict):
            for cron_str, value in sensor.cron.items():
                time = cron_str.split()
                if len(time) == 6:
                    (second, minute, hour, day, month, day_of_week) = time
                elif len(time) == 5:
                    second = '0'
                    (minute, hour, day, month, day_of_week) = time
                else:
                    raise TypeError

                job = self.scheduler.add_job(func=self.sensor_cron_trigger,
                                             trigger=CronTrigger(month=month,
                                                                 day=day,
                                                                 day_of_week=day_of_week,
                                                                 hour=hour,
                                                                 minute=minute,
                                                                 second=second),
                                             args=[sensor, value])
                logging.debug("scheduler: add %s", job)
                if not isinstance(sensor.cron_jobs, list):
                    sensor.cron_jobs = [job]
                else:
                    sensor.cron_jobs.append(job)

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
            yield sensor_id, dict(sensor.get_data(skip_None=False, selected=METRICS))

    def get_metrics(self, skip_None=True):
        for node_id in self.node_id_index:
            for sensor_id, sensor in self.node_id_index[node_id].items():
                yield node_id, sensor_id, dict(
                    sensor.get_data(skip_None=skip_None, selected=METRICS))

    def get_metrics_dict_by_gw(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_metrics(skip_None=skip_None):
            gw = self.__get_sensor(node_id, sensor_id).gw
            if gw not in ret:
                ret[gw] = {}
            if node_id not in ret[gw]:
                ret[gw][node_id] = {}
            if sensor_id not in ret[gw][node_id]:
                ret[gw][node_id][sensor_id] = data
        return ret

    def get_metrics_dict_by_node(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_metrics(skip_None=skip_None):
            if node_id not in ret:
                ret[node_id] = {}
            if sensor_id not in ret[node_id]:
                ret[node_id][sensor_id] = data
        return ret

    def get_metrics_dict_by_sensor(self, skip_None=True):
        ret = {}
        for node_id, sensor_id, data in self.get_metrics(skip_None=skip_None):
            if sensor_id not in ret:
                ret[sensor_id] = {}
            if node_id not in ret[sensor_id]:
                ret[sensor_id][node_id] = data
        return ret

    def get_sensors_dump_dict(self):
        ret = {}
        for sensor in self.sensor_index:
            if sensor.gw not in ret:
                ret[sensor.gw] = {}

            if sensor.node_id not in ret[sensor.gw]:
                ret[sensor.gw][sensor.node_id] = {}

            ret[sensor.gw][sensor.node_id][sensor.sensor_id] = dict(sensor.get_data())
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
            if first[key] != second[key]:  # changed
                if level < 2:
                    changed[key] = self.__get_changed_nodes_dict(first=first[key],
                                                                 second=second[key],
                                                                 level=level + 1)
                else:
                    changed[key] = second[key]

        for key in second:
            if key not in first:  # added
                if level < 2:
                    changed[key] = self.__get_changed_nodes_dict(second=second[key],
                                                                 level=level + 1)
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
                        logging.error("%s.%s: error in eval_require %s", node_id,
                                      sensor_id, sensor.eval_require)
                        return {}

                    search_sensor = self.__get_sensor(node_id, sensor_id)

                    if search_sensor.debounce_dataset and not search_sensor.dataset_ready:
                        logging.debug("skip eval %s.%s: not ready %s.%s in dataset",
                                      sensor.node_id, sensor.sensor_id,
                                      search_sensor.node_id, search_sensor.sensor_id)
                        return {}

                    value = next(search_sensor.get_data(selected={metric_name}))[1]

                    if value is not None:
                        ret[var] = value
                        used_list.append(self.__get_sensor(node_id, sensor_id))
                    else:
                        return {}
            except KeyError:
                logging.debug("skip eval %s.%s: required sensor %s.%s not found",
                              sensor.node_id, sensor.sensor_id, node_id, sensor_id)
                return {}
            except StopIteration:
                logging.debug("skip eval %s.%s: required metric %s of %s.%s not found",
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
                        (sensor_id, _) = tuple(metric_list)  # unused metric_name
                        node_id = s.node_id

                    if node_id == sensor.node_id and sensor_id == sensor.sensor_id and s not in x:
                        x.add(s)
                        yield s

    def __do_requiring_eval(self, sensor, level=0, origin_sensors=None):
        if (level < 8) and (sensor.value != sensor.eval_break_value):
            for req_sensor in self.__get_requiring_sensors(sensor):
                vars_dict = self.__get_sensor_required_vars_dict(req_sensor)

                if not isinstance(origin_sensors, list):
                    new_origin_sensors = [(sensor.node_id, sensor.sensor_id)]
                else:
                    new_origin_sensors = origin_sensors + [
                        (sensor.node_id, sensor.sensor_id)
                    ]

                if req_sensor.do_eval(vars_dict=vars_dict,
                                      origin_list=new_origin_sensors):
                    self.__do_requiring_eval(req_sensor,
                                             level=level + 1,
                                             origin_sensors=new_origin_sensors)

    def __used_dataset_reset(self):
        for s in self.sensor_index:
            if s.dataset_used:
                s.dataset_reset()

    def sensor_cron_trigger(self, sensor, value):
        '''
        called from scheduler when cron time has come
        '''

        logging.info("scheduller run: %s.%s cron time has come", sensor.node_id,
                     sensor.sensor_id)

        # set the same value if None / null
        if value is None:
            x = sensor.value
        else:
            x = value

        self.set_node_values(sensor.node_id, {sensor.sensor_id: x})

    def sensor_expire(self, sensor):
        '''
        called from scheduler job when TTL expires
        '''

        logging.info("scheduller run: %s.%s TTL expired", sensor.node_id,
                     sensor.sensor_id)

        sensor.ttl_job = None
        self.__reset_sensor(sensor)

    def final_changes_processing(self, diff, call_after_expire=False):
        '''
        schedule remaining TTLs
        final emit of changes to SocketIO
          - changed data of sensors to 'events' namespace
          - changed data for actuators to 'metrics' namespace
        '''

        actuator_id_values = {}
        actuator_addr_values = {}

        if isinstance(diff, dict):
            if not diff:
                logging.info('there are no changes')
                return False
        else:
            raise TypeError("not a dict")

        for node_id in diff:
            for sensor_id, metrics in diff[node_id].items():
                sensor = self.__get_sensor(node_id, sensor_id)

                if isinstance(sensor.ttl, int) and isinstance(sensor.hit_timestamp,
                                                              float):

                    ttl_add_job = True
                    ttl_end_job = False
                    if not sensor.default_return_ttl and (sensor.value
                                                          == sensor.default_value):
                        ttl_add_job = False
                        if sensor.value != sensor.prev_value:
                            ttl_end_job = True
                    if call_after_expire and sensor.value == sensor.default_value:
                        ttl_add_job = False
                        ttl_end_job = True

                    if ttl_add_job:
                        ttl_time = datetime.fromtimestamp(
                            sensor.hit_timestamp) + timedelta(seconds=sensor.ttl)
                        sensor.ttl_job = self.scheduler.add_job(
                            func=self.sensor_expire,
                            trigger=DateTrigger(run_date=ttl_time),
                            id='exp-{}-{}'.format(node_id, sensor_id),
                            args=[sensor],
                            replace_existing=True)
                        diff[node_id][sensor_id]['exp_timestamp'] = datetime.timestamp(
                            sensor.ttl_job.next_run_time)

                    if ttl_end_job:
                        diff[node_id][sensor_id]['exp_timestamp'] = None

                if metrics and sensor.mode == ACTUATOR:
                    if sensor.gw not in actuator_id_values:
                        actuator_id_values[sensor.gw] = {}
                    if node_id not in actuator_id_values[sensor.gw]:
                        actuator_id_values[sensor.gw][node_id] = {}
                    actuator_id_values[sensor.gw][node_id][sensor_id] = sensor.value
                    if (sensor.node_addr != '') and (sensor.key != ''):
                        if sensor.gw not in actuator_addr_values:
                            actuator_addr_values[sensor.gw] = {}
                        if sensor.node_addr not in actuator_addr_values[sensor.gw]:
                            actuator_addr_values[sensor.gw][sensor.node_addr] = {}
                        actuator_addr_values[sensor.gw][sensor.node_addr][
                            sensor.key] = sensor.value

        logging.info('final changes: %s', diff)
        self.sio.emit('update_response', json.dumps(diff), namespace=EVENTS_NAMESPACE)

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

        diff2 = self.__get_changed_nodes_dict()
        if diff2:
            logging.debug("scheduler: new ttl jobs: %s", diff2)

        return True

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
                    logging.warning("sensor %s:%s not found in node", node_addr, key)
        return ret

    def set_node_values(self, node_id, sensor_values_dict, increment=False):
        changed = 0

        for sensor_id in sensor_values_dict:

            # create new node if there is a template
            if (node_id not in self.node_id_index) and (sensor_id
                                                        in self.sensor_template_index):
                logging.debug("setup new node %s from template.", node_id)
                self.node_id_index[node_id] = {}
                t = self.sensor_template_index[sensor_id]
                for sx_id, sx in self.node_template_index[t].items():
                    sensor = sx.clone(node_id)
                    self.node_id_index[node_id][sx_id] = sensor
                    self.sensor_index.append(sensor)
                    self.__add_cron_jobs(sensor)

            sensor = self.__get_sensor(node_id, sensor_id)
            if sensor.set(sensor_values_dict[sensor_id], increment=increment):
                changed = 1

                if sensor.eval_code is not None:
                    vars_dict = self.__get_sensor_required_vars_dict(sensor)
                    sensor.do_eval(vars_dict=vars_dict, update=False)

                self.__do_requiring_eval(sensor)
                self.__used_dataset_reset()

        changes = {}
        if changed:
            changes = self.__get_changed_nodes_dict()
            self.final_changes_processing(changes)

        return changes

    def __reset_sensor(self, sensor, skip_eval=False):
        sensor.reset()

        if not sensor.eval_skip_expired and not skip_eval and sensor.value is not None:
            if sensor.eval_code is not None:
                vars_dict = self.__get_sensor_required_vars_dict(sensor)
                sensor.do_eval(vars_dict=vars_dict, update=False)

        self.__do_requiring_eval(sensor)
        self.__used_dataset_reset()
        changes = self.__get_changed_nodes_dict()
        self.final_changes_processing(changes, call_after_expire=True)

    def get_parser_arguments(self):

        d = {}
        for sensor in self.sensor_index:
            t = sensor.get_type()

            if t in (GAUGE, COUNTER):
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
        self.final_changes_processing(changes)

        return changes

    def reset_values(self):
        for sensor in self.sensor_index:
            sensor.__init__()

        changes = self.__get_changed_nodes_dict()
        self.final_changes_processing(changes)

        return changes

    class ConfigException(Exception):
        def __init__(self, message):
            Exception.__init__(self, message)
            self.message = message

    def load_config(self, pars):
        try:
            with open(pars.config_file, 'r') as stream:
                if pars.config_jinja:
                    # load jinja2
                    t = Environment(
                        loader=FileSystemLoader(pars.config_dir)).from_string(
                            stream.read())
                    # load yaml
                    config_dict = safe_load(t.render())
                else:
                    # load yaml
                    config_dict = safe_load(stream)
        except (YAMLError, TemplateSyntaxError, TemplateNotFound,
                FileNotFoundError) as exc:
            raise self.ConfigException("Cant't read config - {}".format(exc))

        self.add_sensors(config_dict)
        changes = self.__get_changed_nodes_dict()
        return changes

    def reload_config(self, pars):
        self.default_values()
        self.reset()
        changes = self.load_config(pars)
        self.final_changes_processing(changes)
        self.sio.emit('reload_response')
        return changes
