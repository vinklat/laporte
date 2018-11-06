from nodes.sensor import Gauge, Counter, Switch, SENSOR, ACTUATOR
from asteval import Interpreter
import logging

# create logger
logger = logging.getLogger('switchboard.node')


class Node():
    '''object that associates sensors'''

    addr = None
    source = None
    mute = None
    accept_refresh = None
    ttl = None

    sensor_dict = {}
    eval_dict = {}
    group_list = []
    watch_list = []

    def get_sensors(self):
        '''generates iterable data from sensors of node'''

        for metric_name in self.sensor_dict:
            sensor = self.sensor_dict[metric_name]
            if sensor.hit_counter >= 0:
                yield ('{}_hits_total'.format(metric_name), sensor.hit_counter)

            if not sensor.hit_interval == None:
                yield ('{}_interval_seconds'.format(metric_name),
                       sensor.hit_interval)

            if not sensor.ttl_remaining == None:
                yield ('{}_ttl_remaining_seconds'.format(metric_name),
                       sensor.ttl_remaining)

            if not sensor.value == None:
                yield (format(metric_name), sensor.value)

    def get_sensors_dict(self):
        '''get data from sensors of node'''

        return dict(self.get_sensors())

    def get_sensors_promexport(self):
        '''generates iterable data from sensors of node (for prometheus export)'''

        for metric_name in self.sensor_dict:
            sensor = self.sensor_dict[metric_name]
            yield ('{}_hits_total'.format(metric_name), sensor.hit_counter,
                   'counter')

            if not sensor.value == None:
                yield (format(metric_name), sensor.value, sensor.get_type())

    def get_sensors_for_eval(self):
        '''generates iterable data from sensors of node (for evaluating)'''

        for metric_name in self.sensor_dict:
            sensor = self.sensor_dict[metric_name]
            if sensor.hit_counter >= 0:
                yield ('{}_hits_total'.format(metric_name), sensor.hit_counter)

            if not sensor.hit_interval == None:
                yield ('{}_interval_seconds'.format(metric_name),
                       sensor.hit_interval)

            if not sensor.value == None:
                yield (format(metric_name), sensor.value)

    def get_sensors_str_for_eval(self):
        '''metrics from sensors in python code string (for evaluating)'''

        ret = ""
        for metric, value in self.get_sensors_for_eval():
            ret += "{}={};\n".format(metric, value)
        return ret

    def get_sensors_for_watch_eval(self):
        '''generates iterable data from sensors of node (for evaluating watching nodes)'''

        for metric_name in self.sensor_dict:
            sensor = self.sensor_dict[metric_name]

            if not sensor.value == None:
                yield (format(metric_name), sensor.value)

    def update_sensors_ttl(self, interval=1):
        '''decrease remaining ttl for sensors of node'''

        change = 0
        for metric_name in self.sensor_dict:
            sensor = self.sensor_dict[metric_name]

            if not sensor.ttl_remaining is None:
                if sensor.dec_ttl(interval):
                    change = 1
        return change

    def get_groups(self):
        '''generates iterable groups of node'''

        if not self.group_list is None:
            for g in self.group_list:
                yield g

    def get_watching(self):
        '''generates iterable watching nodes of node'''

        if not self.watch_list is None:
            for g in self.watch_list:
                yield g

    def set_value(self, metric_name, value):
        '''set value for sensor (metric) of node / used by set_values'''

        try:
            ret = self.sensor_dict[metric_name].set(value)
        except KeyError:
            raise KeyError('{}: sensor not configured'.format(metric_name))

        return ret

    def set_mute(self, mute=True):
        '''set flag for ignoring set_value changes'''

        self.mute = mute

    def set_values(self, values_form):
        '''set values for sensors (metrics) of node'''

        if self.mute is True:
            return {}

        m = {
            "True": True,
            "true": True,
            "ON": True,
            "On": True,
            "on": True,
            "False": False,
            "false": False,
            "OFF": False,
            "Off": False,
            "off": False
        }

        change = 0
        for metric_name in values_form:
            value = values_form[metric_name]

            if type(value) is str:
                try:
                    value = m[value]
                except KeyError:
                    value = float(value)

            if metric_name == 'mute':
                self.set_mute(value)

            else:
                if self.set_value(metric_name, value):
                    change = 1
        return change

    def add_sensor(self, metric_name, sensor):
        '''add initialized sensor to node'''
        self.sensor_dict[metric_name] = sensor

    def add_sensors(self,
                    sensors_form,
                    actuators_form,
                    defaults_form={},
                    ttl_form={},
                    option_params_form={}):
        '''initialize all sensors for node'''

        sensors={**sensors_form, **actuators_form}

        for metric_name in sensors:
            metric_type = sensors[metric_name]

            param = {}

            if metric_name in defaults_form:
                param['default_value'] = defaults_form[metric_name]

            if not type(ttl_form) is dict:
                param['ttl'] = ttl_form
            elif metric_name in ttl_form:
                param['ttl'] = ttl_form[metric_name]

            if metric_name in actuators_form:
                param['mode'] = ACTUATOR

            param.update(option_params_form)

            m = {
                'gauge': Gauge(**param),
                'counter': Counter(**param),
                'switch': Switch(**param)
            }

            s = m[metric_type]

            self.add_sensor(metric_name, s)

    def setup_from_dict(self, source, config_dict):
        '''set up node and its sensors'''

        self.source = source

        try:
            sensors = config_dict['sensors']
        except:
            sensors={}

        try:
            actuators = config_dict['actuators']
        except:
            actuators={}

        if not (sensors or actuators):
            logger.warning('node with no sensors / actuators configured')
        
        try:
            defaults = config_dict['default']
        except KeyError:
            defaults = {}

        try:
            ttl = config_dict['ttl']
        except KeyError:
            ttl = {}

        option_params = {}
        try:
            option_params['accept_refresh'] = config_dict['refresh']
        except KeyError:
            pass

        self.add_sensors(
            sensors,
            actuators,
            defaults_form=defaults,
            ttl_form=ttl,
            option_params_form=option_params)

        # no need it yet
        #try:
        #    self.addr=config_dict['addr']
        #except KeyError:
        #   pass

        try:
            self.group_list = config_dict['group']
        except KeyError:
            pass

        try:
            self.watch_list = config_dict['watch']
        except KeyError:
            pass

        self.eval_dict={}
        try:
            # add defined evals only
            for metric_name in config_dict['eval']:
                if (metric_name in sensors) or (metric_name in actuators):
                    self.eval_dict[metric_name] = config_dict['eval'][metric_name]
                else:
                    logger.warning("{} in eval is not sensor or actuator".format(metric_name))
        except KeyError:
            pass

    def do_eval(self, evalvars=""):
        '''evaluate all eval sensors for node'''

        if self.eval_dict is None:
            return

        change = 0
        for eval_metric_name in self.eval_dict:
            expr = evalvars
            expr += self.get_sensors_str_for_eval()
            expr += self.eval_dict[eval_metric_name]

            logger.debug("evaluating sensor {}:\n{}".format(
                eval_metric_name, expr))

            class Devnull(object):
                def write(self, *_):
                    pass

            aeval = Interpreter(writer=Devnull(), err_writer=Devnull())

            try:
                x = aeval.eval(expr)
            except:
                logger.critical("aeeval {}".format(eval_metric_name))
                break

            if not x is None:
                logger.debug("result: {} = {}".format(eval_metric_name, x))

                if self.sensor_dict[eval_metric_name].set(x):
                    change = 1
            else:
                logger.warning("can't eval {}".format(eval_metric_name))
                if len(aeval.error) > 0:
                    logger.debug(aeval.error[0].get_error())

        return change

    def __init__(self):
        self.sensor_dict = {}
        self.eval_dict = None
        self.group_list = []

        self.mute = None
