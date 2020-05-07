# -*- coding: utf-8 -*-
'''Laporte app version and resources info'''

from platform import python_version
import pkg_resources

__version__ = '0.5.0'


def get_build_info():
    '''get app version and resources info'''
    ret = {
        'laporte':
        __version__,
        'python':
        python_version(),
        'flask':
        pkg_resources.get_distribution('flask').version,
        'flask-restx':
        pkg_resources.get_distribution('flask-restx').version,
        'flask-socketio':
        pkg_resources.get_distribution('flask-socketio').version,
        'python-socketio':
        pkg_resources.get_distribution('python-socketio').version,
        'python-engineio':
        pkg_resources.get_distribution('python-engineio').version,
        'gevent':
        pkg_resources.get_distribution('gevent').version,
        'prometheus_client':
        pkg_resources.get_distribution('prometheus_client').version,
    }
    return ret
