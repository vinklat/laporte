from nodes.node import Node
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
import yaml
import logging

# create logger
logger = logging.getLogger('switchboard.nodes')


class Nodes():
    '''object that associates nodes containing sensors'''

    node_dict = {}
    config_dict = {}
    sio = None

    def load_config(self, filename):
        '''load config of input nodes from yaml file'''

        with open(filename, 'r') as stream:
            try:
                self.config_dict = yaml.load(stream)
            except yaml.YAMLError as exc:
                logger.error(exc)
                return 1


#    def get_config(self):
#        pass

#    def add_node(self, node_id, node):
#        self.node_dict[node_id] = node

    def init_nodes(self):
        '''set up nodes and their sensors'''

        for source in self.config_dict:
            for node_id in self.config_dict[source]:
                n = Node()
                n.setup_from_dict(source, self.config_dict[source][node_id])
                self.node_dict[node_id] = n

    def get_sensors(self):
        '''generates iterable data from sensors of all nodes'''

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            for metric_name, value in node.get_sensors():
                yield node_id, metric_name, value

    def get_sensors_by_node(self):
        '''generates iterable data from sensors of all nodes by node_id'''

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            yield (node_id, dict(node.get_sensors()))

    def get_sensors_dict_by_node(self):
        '''get data from sensors of all nodes by node_id'''

        return dict(self.get_sensors_by_node())

    def get_sensors_dict_by_sensor(self):
        '''get data from sensors of all nodes by sensor (metric) name'''

        ret = {}
        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            for metric_name, value in node.get_sensors():
                try:
                    ret[metric_name][node_id] = value
                except KeyError:
                    ret[metric_name] = {node_id: value}
        return ret

    def get_sensors_dict_by_group(self):
        '''get data from sensors of all nodes by group'''
        ret = {}

        for node_id in self.node_dict:
            node = self.node_dict[node_id]

            x = node.get_sensors_dict()

            for group in node.get_groups():
                if not group in ret:
                    ret[group] = {}
                try:
                    ret[group][node_id] = x
                except KeyError:
                    ret[group] = {node_id: x}
        return ret

    def get_nodes_of_group(self, group):
        '''generates iterable node_ids containing group'''

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            if not node.group_list is None:
                for g in node.group_list:
                    if g == group:
                        yield node_id

    def get_nodes_list_of_group(self, group):
        '''get node_ids containing group'''

        return list(self.get_nodes_of_group(group))

    def get_sensors_of_group(self, group):
        '''generates iterable sensors containing group'''

        sensors = self.get_sensors_dict_by_group()[group]
        for sensor_name in sensors:
            for metric_name in sensors[sensor_name]:
                value = sensors[sensor_name][metric_name]
                yield metric_name, sensor_name, value

    def get_sensors_dict_of_group_by_sensor(self, group):
        '''get sensors containing group by sensor'''

        ret = {}
        for metric_name, sensor_name, value in self.get_sensors_of_group(
                group):
            if not metric_name in ret:
                ret[metric_name] = {}
            ret[metric_name][sensor_name] = value
        return ret

    def get_sensors_dict_of_group_by_node(self, group):
        '''get sensors containing group by node_id'''

        return self.get_sensors_dict_by_group()[group]

    def get_nodes_watching(self, watched_node_id):
        '''generates iterable node_ids watching another specified node'''

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            if not node.watch_list is None:
                for g in node.watch_list:
                    if g == watched_node_id:
                        yield node_id

    def get_sensors_dict_promexport(self):
        '''get data from sensors of all nodes (for prometheus export)'''

        ret = {'gauge': {}, 'counter': {}, 'switch': {}}

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            for metric_name, value, metric_type in node.get_sensors_promexport(
            ):
                try:
                    ret[metric_type][metric_name][node_id] = value
                except KeyError:
                    ret[metric_type][metric_name] = {node_id: value}

        return ret

    def get_config_dict_by_inputs(self):
        '''get all configured inputs'''

        return self.config_dict

    def get_config_dict_input(self, input):
        '''get all nodes of an input'''

        try:
            ret = self.config_dict[input]
        except:
            return {}  #not found
        return ret

    def get_sensors_for_watch_eval(self):
        '''generates iterable data from sensors of nodes (for evaluating)'''

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            yield (node_id, dict(node.get_sensors_for_watch_eval()))

    def get_sensors_str_for_watch_eval(self):
        '''metrics from sensors in python code string (for evaluating)'''

        ret = ""
        nodes = dict(self.get_sensors_for_watch_eval())

        for node_id in nodes:
            sensors = dict(nodes[node_id])

            if sensors:
                ret += "{}={};\n".format(node_id, nodes[node_id])

        return ret

    def sio_emit_actuators(self, node_id, actuators_changed):
        if self.sio is not None:
            self.sio.emit(
                'actuator_response', {node_id: actuators_changed},
                room='mqtt',
                namespace='/metric')

    def do_watching_eval(self, node_id):
        '''evaluate watching nodes of node_id'''

        for x in self.get_nodes_watching(node_id):
            node = self.node_dict[x]
            if node.eval_dict:
                logger.debug("evaluating node {} (watching {})".format(
                    x, node_id))
                foreign_vars = self.get_sensors_str_for_watch_eval()
                actuators_changed = node.do_eval(foreign_vars)
                if actuators_changed:
                    self.sio_emit_actuators(x, actuators_changed)

    def set_values(self, node_id, values_form):
        '''set values for sensors (metrics) of node_id'''

        #state of all sensors before action
        first = self.get_sensors_dict_by_node()

        node = self.node_dict[node_id]
        try:
            change = node.set_values(values_form)
        except KeyError:
            raise KeyError("{}: node not configured".format(node_id))

        if change:
            if node.eval_dict:
                foreign_vars = self.get_sensors_str_for_watch_eval()
                logger.debug("evaluating node {} (after set)".format(node_id))
                #evaluate this node
                actuators_changed = node.do_eval(foreign_vars)
                if actuators_changed:
                    self.sio_emit_actuators(node_id, actuators_changed)

            self.do_watching_eval(node_id)  #evaluate watching nodes

        #state of all sensors after action
        second = self.get_sensors_dict_by_node()

        #get and return dicts diff
        diff = {}

        KEYNOTFOUND = '<KEYNOTFOUND>'
        # Check all keys in first dict
        for key in first.keys():
            if (not key in second):
                diff[key] = (first[key], KEYNOTFOUND)
            elif (first[key] != second[key]):
                diff[key] = (first[key], second[key])

        # Check all keys in second dict to find missing
        for key in second.keys():
            if (not key in first):
                diff[key] = (KEYNOTFOUND, second[key])

        return diff

    def update_sensors_ttl(self, interval=1):
        '''decrease remaining active ttls for sensors of all nodes (called from scheduller)'''

        for node_id in self.node_dict:
            node = self.node_dict[node_id]
            if node.update_sensors_ttl():
                logger.debug("{} ttl timed out".format(node_id))

                if node.eval_dict:
                    foreign_vars = self.get_sensors_str_for_watch_eval()
                    logger.debug(
                        "evaluating node {} (after ttl timeout)".format(
                            node_id))
                    #evaluate this node
                    actuators_changed = node.do_eval(foreign_vars)
                    if actuators_changed:
                        self.sio_emit_actuators(node_id, actuators_changed)

                self.do_watching_eval(node_id)  #evaluate watching nodes

    def __init__(self, filename):
        self.node_dict = {}
        self.load_config(filename)
        self.init_nodes()

    class CustomCollector(object):
        def __init__(self, inner_nodes):
            self.nodes = inner_nodes

        def collect(self):
            exporter_name = "switchboard"
            sensors = self.nodes.get_sensors_dict_promexport()

            for sensor_type in sensors:
                for metric_name in sensors[sensor_type]:
                    if sensor_type == 'counter':
                        x = CounterMetricFamily(
                            '{}_{}'.format(exporter_name, metric_name),
                            '',
                            labels=['node'])
                    else:
                        x = GaugeMetricFamily(
                            '{}_{}'.format(exporter_name, metric_name),
                            '',
                            labels=['node'])

                    for node_id in sensors[sensor_type][metric_name]:
                        value = sensors[sensor_type][metric_name][node_id]
                        x.add_metric([node_id], value)
                    yield x
