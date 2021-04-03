# -*- coding: utf-8 -*-
'''cmd line argument parser for the Laporte http server'''

import logging
import os
from argparse import ArgumentParser, ArgumentTypeError
from .version import __version__, get_version_info

_LOG_LEVEL_STRINGS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']


def log_level_string_to_int(arg_string):
    '''get log level int from string'''

    log_level_string = arg_string.upper()
    if log_level_string not in _LOG_LEVEL_STRINGS:
        message = 'invalid choice: {0} (choose from {1})'.format(
            log_level_string, _LOG_LEVEL_STRINGS)
        raise ArgumentTypeError(message)

    log_level_int = getattr(logging, log_level_string, logging.INFO)
    # check the log_level_choices have not changed from our expected values
    assert isinstance(log_level_int, int)

    return log_level_int


def get_pars():
    '''get parameters from from command line arguments'''

    env_vars = {
        'LISTEN_ADDR': {
            'default': '0.0.0.0'
        },
        'LISTEN_PORT': {
            'default': 9128
        },
        'CONFIG_FILE': {
            'default': 'conf/sensors.yml'
        },
        'CONFIG_JINJA': {
            'default': False
        },
        'CONFIG_DIR': {
            'default': 'conf'
        },
        'LOG_LEVEL': {
            'default': 'DEBUG'
        },
        'LOG_VERBOSE': {
            'default': False
        },
    }

    for env_var, env_pars in env_vars.items():
        if env_var in os.environ:
            if isinstance(env_pars['default'], bool):
                env_vars[env_var]['default'] = bool(os.environ[env_var])
            elif isinstance(env_vars[env_var]['default'], int):
                env_vars[env_var]['default'] = int(os.environ[env_var])
            else:
                env_vars[env_var]['default'] = os.environ[env_var]
            env_vars[env_var]['required'] = False

    parser = ArgumentParser(description='Laporte {}'.format(__version__))
    parser.add_argument('-a',
                        '--listen-address',
                        action='store',
                        dest='listen_addr',
                        help='listen address (default {0})'.format(
                            env_vars['LISTEN_ADDR']['default']),
                        type=str,
                        **env_vars['LISTEN_ADDR'])
    parser.add_argument('-p',
                        '--listen-port',
                        action='store',
                        dest='listen_port',
                        help='listen port (default {0})'.format(
                            env_vars['LISTEN_PORT']['default']),
                        type=int,
                        **env_vars['LISTEN_PORT'])
    parser.add_argument('-c',
                        '--config-file',
                        action='store',
                        dest='config_file',
                        help='yaml or yaml+jinja2 file with '
                        'sensor configuration (default {0})'.format(
                            env_vars['CONFIG_FILE']['default']),
                        type=str,
                        **env_vars['CONFIG_FILE'])
    parser.add_argument('-d',
                        '--config-dir',
                        action='store',
                        dest='config_dir',
                        help='config directory (default {0})'.format(
                            env_vars['CONFIG_DIR']['default']),
                        type=str,
                        **env_vars['CONFIG_DIR'])
    parser.add_argument('-j',
                        '--config-jinja',
                        action='store_true',
                        dest='config_jinja',
                        help='use jinja2 in yaml config file',
                        **env_vars['CONFIG_JINJA'])
    parser.add_argument('-V',
                        '--version',
                        action='version',
                        version=str(get_version_info()))
    parser.add_argument('-l',
                        '--log-level',
                        action='store',
                        dest='log_level',
                        help='set the logging output level. '
                        '{0} (default {1})'.format(_LOG_LEVEL_STRINGS,
                                                   env_vars['LOG_LEVEL']['default']),
                        type=log_level_string_to_int,
                        **env_vars['LOG_LEVEL'])
    parser.add_argument('-v',
                        '--log-verbose',
                        action='store_true',
                        dest='log_verbose',
                        help='most verbose debug level '
                        '(console only; useful for a bug hunt :)',
                        **env_vars['LOG_VERBOSE'])
    return parser.parse_args()


# get parameters from command line arguments
pars = get_pars()
