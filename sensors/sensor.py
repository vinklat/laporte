from abc import ABC, abstractmethod
from asteval import Interpreter
from time import time
import logging

# create logger
logger = logging.getLogger('switchboard.sensor')

SENSOR = 1
ACTUATOR = 2

GAUGE = 1
COUNTER = 2
SWITCH = 3


class Sensor(ABC):
    '''object that associates sensor config, state and related metadata'''

    #config attributes:
    addr = None
    sensor_id = None
    mode = None
    default_value = None
    accept_refresh = None
    ttl = None
    hidden = None
    eval_require = None
    eval_preserve = None
    eval_expr = None
    dataset = None  #not used yet
    eval_require = None
    node_id = None
    source = None

    def setup(self, sensor_id, addr, mode, default_value, accept_refresh, ttl,
              hidden, eval_preserve, eval_expr, dataset, eval_require, node_id,
              source):
        self.addr = addr
        self.sensor_id = sensor_id
        self.mode = mode
        self.default_value = default_value
        self.accept_refresh = accept_refresh
        self.ttl = ttl
        self.hidden = hidden
        self.eval_preserve = eval_preserve
        self.eval_expr = eval_expr
        self.dataset = dataset
        self.eval_require = eval_require
        self.node_id = node_id
        self.source = source

    @abstractmethod
    def get_type(self):
        pass

    def is_actuator(self):
        return self.mode == ACTUATOR

    #state attributes
    value = None
    hits_total = None
    hit_timestamp = None
    interval_seconds = None
    ttl_remaining = None
    data_ready = None
    hold = None
    prev_value = None

    def get_data(self, skip_None=False, selected={}):
        data = self.__dict__

        for x in data:
            if (not selected) or (x in selected):
                if not (data[x] is None and skip_None):
                    yield x, data[x]

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
            self.interval_seconds = timestamp - self.hit_timestamp
        self.hit_timestamp = timestamp

    def set(self, value, update=True):
        value = self.fix_value(value)
        if (value == self.value and not self.accept_refresh) or self.hold:
            return 0

        if update:
            self.prev_value=self.value

        self.value = value

        if update:  #update metadata
            self.count_hit()

            if self.ttl is not None:
                self.ttl_remaining = self.ttl

            if self.dataset:
                self.data_ready = True

        return 1

    def inc(self, value, update=True):
        if self.value is None:
            return self.set(value, update=update)
        else:
            return self.set(self.value + value, update=update)

    def do_eval(self, vars_dict={}, preserve_override=False, update=True):

        if self.eval_expr is None or (self.eval_preserve
                                      and not preserve_override):
            return 0

        if self.eval_require is not None and not vars_dict:
            return 0

        class Devnull(object):
            def write(self, *_):
                pass

        aeval = Interpreter(writer=Devnull(), err_writer=Devnull())

        expr = ""
        for var_node_id in vars_dict:
            expr += "{}={};\n".format(var_node_id, vars_dict[var_node_id])
        for k, v in self.get_data(
                selected={
                    'value', 'prev_value', 'hits_total', 'hit_timestamp', 'interval_seconds',
                    'ttl_remaining'
                }):
            expr += "{}={};\n".format(k, v)

        expr += self.eval_expr

        logger.debug("complete eval expr {}:\n{}".format({ self.node_id: self.sensor_id}, expr))

        try:
            x = aeval.eval(expr)
        except:
            logger.error("aeval {}".format({ self.node_id: self.sensor_id}))
            return 0

        if not x is None:
            logger.info("eval: {}".format( { self.node_id: { self.sensor_id: x}}))
            return self.set(x, update=update)
        else:
            logger.debug("can't eval {}.{}".format(self.node_id,
                                                     self.sensor_id))
            if len(aeval.error) > 0:
                logger.debug(aeval.error[0].get_error())

        return 0

    def dec_ttl(self, interval=1):
        if self.ttl_remaining is not None:
            if self.ttl_remaining > 0:
                self.ttl_remaining -= interval
                return 0
            else:
                self.reset()
                return 1

    def set_hold(self, release=False):
        self.hold = not release


class Gauge(Sensor):
    def get_type(self):
        return GAUGE

    def reset(self):
        self.value = self.default_value
        #self.hits_total = None
        #self.hit_timestamp = None
        #self.interval_seconds = None
        self.ttl_remaining = None
        self.data_ready = False

    def fix_value(self, value):
        if type(value) is str:
            value = float(value)
        return value

    def __init__(self,
                 sensor_id=None,
                 addr=None,
                 mode=SENSOR,
                 default_value=None,
                 accept_refresh=True,
                 ttl=None,
                 hidden=False,
                 eval_preserve=False,
                 eval_expr=None,
                 dataset=False,
                 eval_require=None,
                 node_id=None,
                 source=None):

        self.setup(sensor_id, addr, mode, default_value, accept_refresh, ttl,
                   hidden, eval_preserve, eval_expr, dataset, eval_require,
                   node_id, source)

        self.hold = None
        self.hits_total = 0
        self.hit_timestamp = None
        self.interval_seconds = None
        self.reset()


class Counter(Sensor):
    def get_type(self):
        return COUNTER

    def reset(self):
        self.value = self.default_value
        #self.hits_total = None
        #self.hit_timestamp = None
        #self.interval_seconds = None
        self.ttl_remaining = None
        self.data_ready = False

    def fix_value(self, value):
        if type(value) is str:
            value = float(value)
        return value

    def __init__(
            self,
            sensor_id=None,
            addr=None,
            mode=SENSOR,
            default_value=None,
            accept_refresh=False,  #different than Gauge
            ttl=None,
            hidden=False,
            eval_preserve=False,
            eval_expr=None,
            dataset=False,
            eval_require=None,
            node_id=None,
            source=None):

        self.setup(sensor_id, addr, mode, default_value, accept_refresh, ttl,
                   hidden, eval_preserve, eval_expr, dataset, eval_require,
                   node_id, source)

        self.hold = None
        self.hits_total = 0
        self.hit_timestamp = None
        self.interval_seconds = None
        self.reset()


class Switch(Sensor):
    def get_type(self):
        return SWITCH

    def reset(self):
        self.value = self.default_value
        self.count_hit()
        self.ttl_remaining = None
        self.data_ready = False

    def fix_value(self, value):
        m = {
            "True": True,
            "true": True,
            "ON": True,
            "On": True,
            "on": True,
            "OK": True,
            "Yes": True,
            "yes": True,
            "False": False,
            "false": False,
            "OFF": False,
            "Off": False,
            "off": False,
            "LOW": False,
            "No": False,
            "no": False
        }

        if type(value) is str:
            try:
                value = m[value]
            except KeyError:
                value = bool(value)

        return value

    def __init__(
            self,
            sensor_id=None,
            addr=None,
            mode=SENSOR,
            default_value=False,
            accept_refresh=False,  #different than Gauge
            ttl=None,
            hidden=False,
            eval_preserve=False,
            eval_expr=None,
            dataset=False,
            eval_require=None,
            node_id=None,
            source=None):

        self.setup(sensor_id, addr, mode, default_value, accept_refresh, ttl,
                   hidden, eval_preserve, eval_expr, dataset, eval_require,
                   node_id, source)
        self.hold = None
        self.value = self.default_value
        self.hits_total = 0
        self.ttl_remaining = None
        self.prev_value = self.default_value
