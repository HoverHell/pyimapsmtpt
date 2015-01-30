# coding: utf8
"""
The configuration loader for pyimapsmtpt
"""

import os
import imp


## Cache-singletone
config = None


class Config(object):
    def __init__(self, modules=None):
        self._modules = modules or []

    def __getattr__(self, val):
        sup = object.__getattribute__
        try:
            return sup(self, val)
        except AttributeError as exc:
            exc_ = exc

        for mod in reversed(self._modules):
            try:
                return getattr(mod, val)
            except AttributeError:
                pass

        raise exc_


def get_config(cached=True):
    global config
    if cached and config is not None:
        return config

    import pyimapsmtpt.config_defaults as defaults
    modules = []
    config_file_candidates = defaults.config_files
    for candidate in config_file_candidates:
        if os.path.exists(candidate):
            try:
                mod = imp.load_source('config', candidate)
            except Exception as exc:
                print "ERROR: could not import %r: %r" % (candidate, exc)
                continue
            modules.append(mod)
            break

    if not modules:
        raise Exception(("User-overrides config is required. See %r for the"
                         " allowed loactions") % (defaults.__file__,))

    config = Config([defaults] + modules)
    return config
