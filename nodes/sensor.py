from abc import ABC, abstractmethod
from time import time

SENSOR = 1
ACTUATOR = 2


class Metric(ABC):
    '''object that associates metric value and related counters / flags / config'''
    addr = None
    mode = None
    ttl = None
    accept_refresh = None

    value = None
    hit_counter = None
    hit_timestamp = None
    hit_interval = None
    ttl_remaining = None

    @abstractmethod
    def get_type(self):
        pass

    @abstractmethod
    def reset(self):
        pass

    def count_hit(self):
        if self.hit_counter is None:
            self.hit_counter = 1
        else:
            self.hit_counter += 1

        timestamp = time()
        if not self.hit_timestamp is None:
            self.hit_interval = timestamp - self.hit_timestamp
        self.hit_timestamp = timestamp

    def set(self, value):
        if value == self.value and not self.accept_refresh:
            return 0

        if self.ttl is not None:
            self.ttl_remaining = self.ttl

        self.value = value
        self.count_hit()
        return 1

    def inc(self, value):
        if self.value is None:
            self.value = 0
        self.value += value
        self.count_hit()

    def dec_ttl(self, interval=1):
        if self.ttl_remaining is not None:
            if self.ttl_remaining > 0:
                self.ttl_remaining -= interval
                return 0
            else:
                self.reset()
                return 1

    def is_actuator(self):
        return self.mode == ACTUATOR


class Gauge(Metric):
    def get_type(self):
        return 'gauge'

    def reset(self):
        self.value = self.default_value
        self.hit_counter = 0
        self.ttl_remaining = None

    def __init__(self,
                 addr=None,
                 mode=SENSOR,
                 ttl=None,
                 accept_refresh=True,
                 default_value=None,
                 hit_counter=0):
        #Metric.__init__(self)
        self.addr = addr
        self.mode = mode
        self.ttl = ttl
        self.accept_refresh = accept_refresh
        self.value = default_value
        self.default_value = default_value
        self.hit_counter = hit_counter
        self.ttl_remaining = None


class Counter(Metric):
    def get_type(self):
        return 'counter'

    def reset(self):
        self.value = self.default_value
        self.hit_counter = 0
        self.ttl_remaining = None

    def __init__(self,
                 addr=None,
                 mode=SENSOR,
                 ttl=None,
                 accept_refresh=False,
                 default_value=None,
                 hit_counter=0):
        self.addr = addr
        self.mode = mode
        self.ttl = ttl
        self.accept_refresh = accept_refresh
        self.value = default_value
        self.default_value = default_value
        self.hit_counter = hit_counter
        self.ttl_remaining = None


class Switch(Metric):
    def get_type(self):
        return 'switch'

    def reset(self):
        self.value = self.default_value
        self.count_hit()
        self.ttl_remaining = None

    def __init__(self,
                 addr=None,
                 mode=SENSOR,
                 ttl=None,
                 accept_refresh=False,
                 default_value=False,
                 hit_counter=0):
        self.addr = addr
        self.mode = mode
        self.ttl = ttl
        self.accept_refresh = accept_refresh
        self.value = default_value
        self.default_value = default_value
        self.hit_counter = hit_counter
        self.ttl_remaining = None
