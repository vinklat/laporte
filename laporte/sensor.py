# -*- coding: utf-8 -*-
'''objects that collect config and internal states of one sensor'''

import re
# import numpy as np
import logging
from copy import copy
from abc import ABC, abstractmethod
from time import time
from asteval import Interpreter, make_symbol_table

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

SENSOR = 1
ACTUATOR = 2

GAUGE = 1
COUNTER = 2
SWITCH = 3
MESSAGE = 4


class Sensor(ABC):
    '''abstract base class for Gauge, Counter, Switch and Message class'''

    # config attributes:
    node_addr = None
    key = None
    sensor_id = None
    mode = None
    default_value = None
    accept_refresh = None
    ttl = None
    export_sensor_id = None
    export_node_id = None
    export_labels = None
    export_hidden = None
    eval_require = None
    eval_preserve = None
    eval_expr = None
    dataset = None
    node_id = None
    gw = None

    def setup(self, sensor_id, node_addr, key, mode, default_value,
              accept_refresh, ttl, export, parent_export, eval_preserve,
              eval_expr, dataset, eval_require, node_id, gw):
        '''assign values to the data members of the class'''

        self.node_addr = node_addr
        self.key = key
        self.sensor_id = sensor_id
        self.mode = mode
        self.default_value = default_value
        self.accept_refresh = accept_refresh
        self.ttl = ttl
        self.eval_preserve = eval_preserve
        self.eval_expr = eval_expr
        self.dataset = dataset
        self.eval_require = eval_require
        self.node_id = node_id
        self.gw = gw

        self.export_sensor_id = sensor_id
        self.export_node_id = node_id
        self.export_hidden = False
        self.export_labels = {}

        self.set_export(export, parent_export)

    def set_export(self, export, parent_export):
        '''set export related attributes  - labels and others'''

        # if node is a template
        if isinstance(self.node_id, int):
            self.parent_export = parent_export
            self.export = export
            return

        if isinstance(parent_export, dict):
            if 'hidden' in parent_export:
                self.export_hidden = parent_export['hidden']

            if 'labels' in parent_export:
                for label, label_value in parent_export['labels'].items():
                    if isinstance(label_value, int):
                        parts = self.node_id.split('_', label_value)
                        self.export_labels[label] = parts[label_value - 1]
                        self.export_node_id = parts[label_value]
                    if isinstance(label_value, str):
                        self.export_labels[label] = label_value

        if isinstance(export, dict):
            if 'hidden' in export:
                self.export_hidden = export['hidden']

            if 'labels' in export:
                for label, label_value in export['labels'].items():
                    if isinstance(label_value, int):
                        parts = self.sensor_id.split('_', label_value)
                        self.export_labels[label] = parts[label_value - 1]
                        self.export_sensor_id = parts[label_value]
                    if isinstance(label_value, str):
                        self.export_labels[label] = label_value

    def clone(self, new_node_id):
        '''
        clone sensor with a new node_id
        reset export attributes if sensor is a templete
        '''

        ret = copy(self)
        ret.node_id = new_node_id
        ret.export_node_id = new_node_id

        # if node is a template
        if isinstance(self.node_id, int):
            ret.set_export(ret.export, ret.parent_export)
            del ret.export
            del ret.parent_export

        return ret

    @abstractmethod
    def get_type(self):
        pass

    def is_actuator(self):
        return self.mode == ACTUATOR

    # state attributes
    value = None
    prev_value = None
    hits_total = None
    hit_timestamp = None
    duration_seconds = None
    ttl_remaining = None
    dataset_ready = None
    dataset_used = None
    hold = None

    def get_data(self, skip_None=False, selected={}):
        z = {**self.__dict__, **{'type': self.get_type()}}
        for key, value in z.items():
            if (not selected) or (key in selected):
                if not (value is None and skip_None):
                    yield key, value

    def get_promexport_data(self):
        t = self.get_type()
        labels = []
        label_values = []
        for label, label_value in self.export_labels.items():
            labels.append(label)
            label_values.append(label_value)

        if self.value is not None:
            yield self.export_sensor_id, t, self.value, ['node'] + labels, [
                self.export_node_id
            ] + label_values
        if self.hits_total is not None:
            yield 'hits_total', COUNTER, self.hits_total, [
                'node', 'sensor'
            ] + labels, [self.export_node_id, self.export_sensor_id
                         ] + label_values
        if self.duration_seconds is not None:
            yield 'duration_seconds', COUNTER, self.duration_seconds, [
                'node', 'sensor'
            ] + labels, [self.export_node_id, self.export_sensor_id
                         ] + label_values

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def fix_value(self, value):
        pass

    def count_hit(self):
        if self.hits_total is None:
            self.hits_total = 1
        else:
            self.hits_total += 1

        timestamp = time()
        if not self.hit_timestamp is None:
            self.duration_seconds = timestamp - self.hit_timestamp
        self.hit_timestamp = timestamp

    def set(self, value, update=True, increment=False):
        value = self.fix_value(value)

        if (increment and self.value is not None):
            value += self.value

        if (value == self.value and not self.accept_refresh) or self.hold:
            return 0

        if update:
            self.prev_value = self.value

        self.value = value

        if update:  # update metadata
            self.count_hit()

            if self.ttl is not None:
                if self.get_type() == SWITCH and value == self.default_value:
                    self.ttl_remaining = None
                else:
                    self.ttl_remaining = self.ttl

            if self.dataset:
                self.dataset_ready = True

        return 1

    def do_eval(self, vars_dict={}, preserve_override=False, update=True):

        if self.eval_expr is None or (self.eval_preserve
                                      and not preserve_override):
            return 0

        if self.eval_require is not None and not vars_dict:
            return 0

        class Devnull(object):
            def write(self, *_):
                pass

        syms = make_symbol_table(
            use_numpy=True,
            **vars_dict,
            **dict(
                self.get_data(
                    selected={
                        'value', 'prev_value', 'hits_total', 'hit_timestamp',
                        'duration_seconds', 'ttl_remaining'
                    })),
            re=re)

        aeval = Interpreter(writer=Devnull(),
                            err_writer=Devnull(),
                            symtable=syms)

        try:
            x = aeval.eval(self.eval_expr)
        except:
            logging.error("aeval {}".format({self.node_id: self.sensor_id}))
            return 0

        if not x is None:
            logging.info("eval: {}".format({self.node_id: {
                self.sensor_id: x
            }}))
            return self.set(x, update=update)

        logging.debug("can't eval {}.{}".format(self.node_id, self.sensor_id))
        if len(aeval.error) > 0:
            logging.debug(aeval.error[0].get_error())

        return 0

    def dataset_use(self):
        if self.dataset:
            self.dataset_used = True

    def dataset_reset(self):
        if self.dataset:
            self.dataset_ready = False
            self.dataset_used = False

    def dec_ttl(self, interval=1):
        if self.ttl_remaining is not None:
            if self.ttl_remaining > 0:
                self.ttl_remaining -= interval
                return 0
            self.reset()  # else
            return 1
        return 0

    def set_hold(self, release=False):
        self.hold = not release


class Gauge(Sensor):
    '''An object that collects state and metadata of the Gauge sensor.
       A gauge is a metric that represents a single numerical value that can arbitrarily go up and down.
    '''

    def get_type(self):
        return GAUGE

    def reset(self):
        self.value = self.default_value
        self.ttl_remaining = None
        self.dataset_ready = False
        self.dataset_used = False

    def fix_value(self, value):
        if isinstance(value, str):
            value = float(value)
        return value

    def __init__(self,
                 sensor_id=None,
                 node_addr=None,
                 key=None,
                 mode=SENSOR,
                 default_value=None,
                 accept_refresh=True,
                 ttl=None,
                 export=False,
                 parent_export=False,
                 eval_preserve=False,
                 eval_expr=None,
                 dataset=False,
                 eval_require=None,
                 node_id=None,
                 gw=None):

        self.setup(sensor_id, node_addr, key, mode, default_value,
                   accept_refresh, ttl, export, parent_export, eval_preserve,
                   eval_expr, dataset, eval_require, node_id, gw)

        self.hold = None
        self.hits_total = 0
        self.hit_timestamp = None
        self.duration_seconds = None
        self.reset()


class Counter(Sensor):
    '''An object that collects state and metadata of the Counter type sensor.
       A counter is a cumulative metric that represents a single monotonically
       increasing counter whose value can only increase or be reset to zero.
    '''

    def get_type(self):
        return COUNTER

    def reset(self):
        self.value = self.default_value
        self.ttl_remaining = None
        self.dataset_ready = False
        self.dataset_used = False

    def fix_value(self, value):
        if isinstance(value, str):
            value = float(value)
        return value

    def __init__(self,
                 sensor_id=None,
                 node_addr=None,
                 key=None,
                 mode=SENSOR,
                 default_value=None,
                 accept_refresh=False,
                 ttl=None,
                 export=False,
                 parent_export=False,
                 eval_preserve=False,
                 eval_expr=None,
                 dataset=False,
                 eval_require=None,
                 node_id=None,
                 gw=None):

        self.setup(sensor_id, node_addr, key, mode, default_value,
                   accept_refresh, ttl, export, parent_export, eval_preserve,
                   eval_expr, dataset, eval_require, node_id, gw)

        self.hold = None
        self.hits_total = 0
        self.hit_timestamp = None
        self.duration_seconds = None
        self.reset()


class Switch(Sensor):
    '''An object that collects state and metadata of the Switch type sensor
       The switch is a metric that represents a single boolean 
       value On/Off (True/False).
    '''

    def get_type(self):
        return SWITCH

    def reset(self):
        self.value = self.default_value
        self.count_hit()
        self.ttl_remaining = None

    def fix_value(self, value):
        values_map = {
            'True': True,
            'true': True,
            'ON': True,
            'On': True,
            'on': True,
            'OK': True,
            'Yes': True,
            'yes': True,
            '1': True,
            'False': False,
            'false': False,
            'OFF': False,
            'Off': False,
            'off': False,
            'LOW': False,
            'No': False,
            'no': False,
            '0': False
        }

        if isinstance(value, str):
            try:
                value = values_map[value]
            except KeyError:
                value = bool(value)

        return value

    def __init__(self,
                 sensor_id=None,
                 node_addr=None,
                 key=None,
                 mode=SENSOR,
                 default_value=False,
                 accept_refresh=False,
                 ttl=None,
                 export=False,
                 parent_export=False,
                 eval_preserve=False,
                 eval_expr=None,
                 dataset=False,
                 eval_require=None,
                 node_id=None,
                 gw=None):

        self.setup(sensor_id, node_addr, key, mode, default_value,
                   accept_refresh, ttl, export, parent_export, eval_preserve,
                   eval_expr, dataset, eval_require, node_id, gw)
        self.hold = None
        self.value = self.default_value
        self.prev_value = self.default_value
        self.hits_total = 0
        self.duration_seconds = None
        self.hit_timestamp = None
        self.ttl_remaining = None
        self.dataset_ready = False
        self.dataset_used = False


class Message(Sensor):
    '''An object that collects state and metadata of the Message (string) sensor.
       This is not a metric but represents a text string that can be displayed
       or parsed to metric.
    '''

    def get_type(self):
        return MESSAGE

    def reset(self):
        self.value = self.default_value
        self.ttl_remaining = None
        self.dataset_ready = False
        self.dataset_used = False

    def fix_value(self, value):
        return value

    def __init__(self,
                 sensor_id=None,
                 node_addr=None,
                 key=None,
                 mode=SENSOR,
                 default_value='',
                 accept_refresh=False,
                 ttl=None,
                 export=False,
                 parent_export=False,
                 eval_preserve=False,
                 eval_expr=None,
                 dataset=False,
                 eval_require=None,
                 node_id=None,
                 gw=None):

        self.setup(sensor_id, node_addr, key, mode, default_value,
                   accept_refresh, ttl, export, parent_export, eval_preserve,
                   eval_expr, dataset, eval_require, node_id, gw)
        self.hold = None
        self.value = self.default_value
        self.prev_value = self.default_value
        self.hits_total = 0
        self.duration_seconds = None
        self.hit_timestamp = None
        self.ttl_remaining = None
        self.export_hidden = True
