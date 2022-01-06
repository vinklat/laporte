# -*- coding: utf-8 -*-
'''Laporte app version and resources info'''

from datetime import datetime
from platform import python_version
import os
import pkg_resources

__version__ = '0.7.3'
app_name = 'laporte'

start_timestamp = datetime.now().isoformat()


def get_version_info():
    '''get app version info'''

    ret = {
        'version': __version__,
    }

    return ret


def get_runtime_info():
    '''get app and resources runtime info'''

    modules = {
        'flask': pkg_resources.get_distribution('flask').version,
        'flask-restx': pkg_resources.get_distribution('flask-restx').version,
        'flask-socketio': pkg_resources.get_distribution('flask-socketio').version,
        'python-socketio': pkg_resources.get_distribution('python-socketio').version,
        'python-engineio': pkg_resources.get_distribution('python-engineio').version,
        'gevent': pkg_resources.get_distribution('gevent').version,
        'prometheus_client': pkg_resources.get_distribution('prometheus_client').version,
    }

    runtime = {
        'start_timestamp': start_timestamp,
        'python_version': python_version(),
    }

    ret = {**get_version_info(), **runtime, 'python_modules': modules}

    _RUNTIME_ENVS = ['HOSTNAME']

    for env in _RUNTIME_ENVS:
        if env in os.environ:
            ret[env] = os.environ[env]

    return ret
