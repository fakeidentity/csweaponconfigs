# -*- coding: utf-8 -*-

import os
from configparser import SafeConfigParser, NoSectionError
from random import choice
from logging import getLogger

import port_for
import appdirs

from log import modulename
from utils import bind_data, unused_binds, our_cfg_fn
from __init__ import appname

log = getLogger(modulename())
log.debug("Helo its me ur config")

config_dir = appdirs.user_config_dir(appname, False)
configfn = f"{appname}.ini"
config_path = os.path.join(config_dir, configfn)

# Default values

# I just think using 27000~ is neat.. hopefully this doesn't cause problems?
_steamish_ports = {p for p in port_for.available_good_ports() if \
                  str(p).startswith("270") and \
                  len(str(p)) == 5}
def default_gsi_port():
    log.debug("Looking for an appropriate default GSI endpoint server port")
    try:
        port = port_for.select_random(_steamish_ports)
    except port_for.exceptions.PortForException:
        log.debug("Couldn't find free port in the 'steamish' range.")
        # broaden the scope..
        port = port_for.select_random()
    return port


def default_bind():
    log.debug("Picking a default bind")
    binds = bind_data()
    lookfor = "exec {}".format(our_cfg_fn.rpartition(".")[0])
    try:
        existing_bind = next(k for k, v in binds.items() \
                             if lookfor in v)
    except StopIteration:
        # no existing bind. normal.
        pass
    else:
        log.debug(f"{existing_bind} is already bound to exec our script, "
                  "so we can use that!")
        return existing_bind

    _unused_binds = unused_binds(binds)
    ideal_unused_binds = [b for b in _unused_binds if "LOCK" not in b]
    bind = choice(ideal_unused_binds or _unused_binds)
    log.debug(f"{bind} is our choice of unused bind.")
    return bind


data = {
    "cs_bind": default_bind,
    "gsi_port": default_gsi_port,
}


def get_config():
    config = SafeConfigParser()
    if not user_config_exists():
        generate_config()
    config.read([config_path])
    return config


def user_config_exists():
    return os.path.isfile(config_path)


def generate_config(configdata=None):
    global _old_data

    if not configdata:
        configdata = data

    for k, v in data.items():
        if callable(v):
            data[k] = v()

    config = SafeConfigParser(allow_no_value=True)

    config.add_section(appname)
    config.set(appname, "; CS bind name for the script to use.")
    config.set(appname, ("; Pick something you don't already have bound, "
                         "and don't ever want to use."))
    config.set(appname, ("; Possible binds include A–Z, 0–9, TAB, KP_PLUS, etc."
                         " See https://developer.valvesoftware.com/wiki/Bind"))
    config.set(appname, "cs_bind", configdata["cs_bind"])

    config.set(appname, "; What port to run the GSI endpoint server on?")
    config.set(appname, ("; This intelligently defaults to a port that is "
                         "unused, and likely to stay unused. "
                         "You shouldn't need to change it."))
    config.set(appname, "gsi_port", str(configdata["gsi_port"]))

    write_cfg(config)
    _old_data = configdata.copy()


def write_cfg(config, config_fp=config_path):
    # save / write to file
    log.debug(f"Writing config file to {config_path}.")
    os.makedirs(config_dir, exist_ok=True)
    with open(config_fp, "w", encoding="utf-8") as f:
        config.write(f)


config = get_config()

_require_regen = False
num_options_in_file = 0
try:
    for setting_name in config.options(appname):
        num_options_in_file += 1

        val = config.get(appname, setting_name)

        # take care of any idiots' problems before they start
        if val.startswith('"') and val.endswith('"') or \
           val.startswith("'") and val.endswith("'"):
            log.warning("Some idiot put quotes around the value of "
                     f"{setting_name} in the config file. We'll fix it.")
            val = val[1:-1]
            _require_regen = True

        data[setting_name] = val
except NoSectionError:
    log.warning(f"No {appname} section in config. Maybe somebody fucked it up? "
                "It'll fix itself.")

_old_data = data.copy()

log.debug(data)

# Ensure any missing elements are written to file.
# Everything will work without this, but I think it's nicer to automagically
#  fix the file than to continually work around a broken one.
if len(data) > num_options_in_file:
    log.debug("Config file is missing one or more options. "
              "Generating a new file. Old settings carry over.")
    _require_regen = True

if _require_regen:
    generate_config()

def has_changed():
    if _old_data != data:
        return True
    return False
