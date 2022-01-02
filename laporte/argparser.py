# -*- coding: utf-8 -*-
'''cmd line argument parser for the Laporte http server'''

import logging
import os
from argparse import ArgumentParser, ArgumentTypeError
from laporte.version import __version__, app_name, get_version_info

LOG_LEVEL_STRINGS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
LOG_LEVEL_DEFAULT = 'DEBUG'
LOG_VERBOSE_DEFAULT = False
LISTEN_ADDR_DEFAULT = '0.0.0.0'
LISTEN_PORT_DEFAULT = 9128
CONFIG_DIR_DEFAULT = 'conf'
CONFIG_FILE_DEFAULT = 'conf/sensors.yml'
CONFIG_JINJA_DEFAULT = False


def log_level_string_to_int(arg_string: str) -> int:
    '''get log level int from string'''

    log_level_string = arg_string.upper()
    if log_level_string not in LOG_LEVEL_STRINGS:
        message = (f"invalid choice: {log_level_string} "
                   f"(choose from {LOG_LEVEL_STRINGS})")
        raise ArgumentTypeError(message)

    log_level_int = getattr(logging, log_level_string, logging.INFO)
    # check the log_level_choices have not changed from our expected values
    assert isinstance(log_level_int, int)

    return log_level_int


def get_pars():
    '''get parameters from from command line arguments'''

    env_vars = {
        'LISTEN_ADDR': {
            'default': LISTEN_ADDR_DEFAULT
        },
        'LISTEN_PORT': {
            'default': LISTEN_PORT_DEFAULT
        },
        'CONFIG_FILE': {
            'default': CONFIG_FILE_DEFAULT
        },
        'CONFIG_JINJA': {
            'default': CONFIG_JINJA_DEFAULT
        },
        'CONFIG_DIR': {
            'default': CONFIG_DIR_DEFAULT
        },
        'LOG_LEVEL': {
            'default': LOG_LEVEL_DEFAULT
        },
        'LOG_VERBOSE': {
            'default': LOG_VERBOSE_DEFAULT
        },
    }

    # defaults overriden from ENVs
    for env_var, env_pars in env_vars.items():
        if env_var in os.environ:
            default = os.environ[env_var]
            if 'default' in env_pars:
                if isinstance(env_pars['default'], bool):
                    default = bool(os.environ[env_var])
                elif isinstance(env_pars['default'], int):
                    default = int(os.environ[env_var])
            env_pars['default'] = default
            env_pars['required'] = False

    parser = ArgumentParser(description=f'{app_name.capitalize()} {__version__}')
    parser.add_argument('-a',
                        '--listen-address',
                        action='store',
                        dest='listen_addr',
                        help=f"listen address (default {LISTEN_ADDR_DEFAULT})",
                        type=str,
                        **env_vars['LISTEN_ADDR'])
    parser.add_argument('-p',
                        '--listen-port',
                        action='store',
                        dest='listen_port',
                        help=f"listen port (default {LISTEN_PORT_DEFAULT})",
                        type=int,
                        **env_vars['LISTEN_PORT'])
    parser.add_argument('-c',
                        '--config-file',
                        action='store',
                        dest='config_file',
                        help=("yaml or yaml+jinja2 file with "
                              f"sensor configuration (default {CONFIG_DIR_DEFAULT})"),
                        type=str,
                        **env_vars['CONFIG_FILE'])
    parser.add_argument('-d',
                        '--config-dir',
                        action='store',
                        dest='config_dir',
                        help=f"config directory (default {CONFIG_DIR_DEFAULT})",
                        type=str,
                        **env_vars['CONFIG_DIR'])
    parser.add_argument('-j',
                        '--config-jinja',
                        action='store_true',
                        dest='config_jinja',
                        help=("use jinja2 in yaml config file "
                              f"(default {CONFIG_JINJA_DEFAULT}"),
                        **env_vars['CONFIG_JINJA'])
    parser.add_argument('-V',
                        '--version',
                        action='version',
                        version=str(get_version_info()))
    parser.add_argument('-l',
                        '--log-level',
                        action='store',
                        dest='log_level',
                        help=("set the logging output levelx "
                              f"{LOG_LEVEL_STRINGS} (default {LOG_LEVEL_DEFAULT})"),
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
