__author__ = 'magus0219'

import importlib
import sys
import types

def load_config_by_env(env):
    """load specified configuration file

    Load names of specified configuration file into this config namespace
    :param env: Name of environment choices of 'development','test','production'
    :return: None
    """
    config_mod = importlib.import_module('.' + env, 'config')
    for attr in config_mod.__dict__:

        if not attr.startswith('__') and not isinstance(attr, types.ModuleType):
            setattr(sys.modules[__name__], attr, config_mod.__dict__[attr])