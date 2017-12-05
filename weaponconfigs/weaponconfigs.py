# -*- coding: utf-8 -*-

import sys
from threading import Thread
from functools import partial, lru_cache
import json
import os
from textwrap import dedent
from http import HTTPStatus
import logging
from subprocess import Popen, call
import re

from flask import Flask, request
import jinja2
from jinja2 import Template
import click
from click import echo, secho, confirm, pause
import autoit
import appdirs
from colorama import Fore
from win32console import SetConsoleTitle

from log import logger_setup, handle_exception
from __init__ import appname, __version__, appurl

current_dir = os.path.dirname(os.path.realpath(__file__))
data_dir = current_dir
log_dir = appdirs.user_log_dir(appname, False)
log = logger_setup(log_dir, __file__)
uncaught_exception_handler = partial(handle_exception, log)
sys.excepthook = uncaught_exception_handler

log.info(f"{appname} - version {__version__}")

from utils import (active_window_title, list_open_windows, cs_bind_autoit_map,
                   cs_cfg_dir, our_cfg_fp, execsnippet, existing_binds,
                   prettylist, launch_options,autoexec_filename, steam_dir,
                   set_launch_options, add_to_autoexec, tray_icon, convis)
import config
port = config.data["gsi_port"]
cs_bind = config.data["cs_bind"]

fapp = Flask(__name__)

# Make flask log to our log file
for loghandler in log.handlers:
    if isinstance(loghandler, logging.FileHandler):
        fapp.logger.addHandler(loghandler)

gsi_config_fn = "gamestate_integration_weapon_configs.cfg"
gsi_config_fp = os.path.join(cs_cfg_dir, gsi_config_fn)
gsi_cfg_template_fn = gsi_config_fn + ".template"
gsi_cfg_template_fp = os.path.join(data_dir, gsi_cfg_template_fn)
game_name = "Counter-Strike: Global Offensive"

def render_from_file(tpl_path, *args, **kwargs):
    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(path or './')
        ).get_template(filename).render(*args, **kwargs)


class GSIPayloadHandler(object):
    id_line = f"// created by {appname}"
    if appurl:
        id_line += f" ({appurl})"

    cfg_template = Template(dedent("""
        // This file is overwritten every time you change weapon. Don't bother editing it.
        {%- if wep_slot != last_wep_slot %}
        exec {{wep_slot}} // weapon slot (slot1–slot10)
        {%- endif %}
        {%- if wep_type and wep_type != last_wep_type %}
        exec {{wep_type}} // weapon type ("pistol", "rifle", "submachinegun", "sniperrifle", "machinegun", "shotgun", "c4", "knife", "grenade")
        {%- endif %}
        {%- if wep_type != wep_name %}
        exec {{wep_name}} // weapon name (without "weapon_" prefix)
        {%- endif %}
        {{id_line}}
        """).strip())

    def __init__(self):
        self.last_wep_name = ""
        self.last_wep_slot = ""
        self.last_wep_type = ""
        self.setxhair_queued = False
        self.active_wep_type = ""
        self.active_wep_name = ""
        self.active_wep_slot = ""
        self.last_activity = ""


    def process(self, data):
        if data["provider"]["name"] != game_name:
            return
        activity = data.get("player", {}).get("activity", "") # "player_id" 0 in gamestate_integration cfg
        if not activity:
            log.warning(
                Fore.RED +
                "No 'activity' data. Check \"player_id\" is \"1\" "
                "in gamestate_integration_weaponconfigs.cfg.\n"
                "We need 'activity' to determine if console is open or not." +
                Fore.RESET
            )
        elif activity == "menu": # no weapons in menu
            log.info("In menu.") # ok as INFO thanks to dupe log filter
            return
        elif self.setxhair_queued and activity == "playing":
            if self.last_activity == "textinput":
                log.debug("Console must've closed.")
            self.press_bind()
        self.last_activity = activity
        weapons = data["player"]["weapons"]
        for wep in weapons:
            if weapons[wep]["state"] != "active":
                continue
            self.active_wep_type = weapons[wep].get("type", "") # taser doesn't have a type
            self.active_wep_name = weapons[wep]["name"]
            self.active_wep_name = self.active_wep_name.partition("weapon_")[-1]
            self.active_wep_name = self.active_wep_name.lower()
            self.active_wep_type = self.active_wep_type.lower()
            self.active_wep_type = self.active_wep_type.replace(" ", "")

            if self.active_wep_name == self.last_wep_name:
                return
            else:
                self.last_wep_name = self.active_wep_name

            log.info(f"{self.active_wep_name} is active.")

            self.active_wep_slot = ""
            if self.active_wep_type in ["rifle", "submachinegun",
                                        "sniperrifle", "machinegun",
                                        "shotgun"]:
                self.active_wep_slot = "slot1"
            elif self.active_wep_type == "pistol":
                self.active_wep_slot = "slot2"
            elif (self.active_wep_type == "knife"
                  or self.active_wep_name == "taser"):
                self.active_wep_slot = "slot3"
            elif self.active_wep_type == "c4":
                self.active_wep_slot = "slot5"
            elif self.active_wep_name == "hegrenade":
                self.active_wep_slot = "slot6"
            elif self.active_wep_name == "flashbang":
                self.active_wep_slot = "slot7"
            elif self.active_wep_name == "smokegrenade":
                self.active_wep_slot = "slot8"
            elif self.active_wep_name == "decoy":
                self.active_wep_slot = "slot9"
            elif (self.active_wep_name == "incgrenade"
                  or self.active_wep_name == "molotov"):
                self.active_wep_slot = "slot10"

            self.make_cfg()

            self.last_wep_slot = self.active_wep_slot
            self.last_wep_type = self.active_wep_type

            if activity == "playing":
                self.press_bind()
            elif activity == "textinput":
                log.info("Can't press bind yet because console is open.")
                # don't just use self.last_wep_name = ""
                # coz then weapon_configs.cfg would get (re)written constantly
                self.setxhair_queued = True


    def press_bind(self):
        if active_window_title() == game_name:
            log.info(f"Pressing {cs_bind}.")
            autoit.send(cs_bind_autoit_map[cs_bind])
            self.setxhair_queued = False
        else:
            log.info("Game not focused. Not pressing bind.")
            self.setxhair_queued = True


    def gen_cfg(self):
        s = self.cfg_template.render(last_wep_slot = self.last_wep_slot,
                                     wep_slot = self.active_wep_slot,
                                     last_wep_type = self.last_wep_type,
                                     wep_type = self.active_wep_type,
                                     wep_name = self.active_wep_name,
                                     id_line = self.id_line)
        log.debug(s)
        return s


    def make_cfg(self):
        def write_cfg(overwrite=True):
            if overwrite:
                mode = "w"
            else:
                mode = "x"
            with open(our_cfg_fp, mode, encoding="utf-8") as f:
                f.write(self.gen_cfg())
        log.debug(f"Attempting to make CFG file: {our_cfg_fp}")
        try: # Assume file doesn't exist and try to make it
            write_cfg(overwrite=False)
            log.debug("Successfully wrote NEW CFG file.")
        except FileExistsError:
            log.debug("CFG file exists already.")
            # File exists. It's probably an old copy of ours.
            # Check to make sure it's not a coincedentally named, unrelated file
            with open(our_cfg_fp, "r") as f:
                if self.id_line in f.read():
                    # Our file. Good. Overwrite it.
                    log.debug("Existing CFG file is ours. Overwriting.")
                    write_cfg()
                    log.debug("Overwrote CFG file.")
                elif os.path.getsize(our_cfg_fp) == 0:
                    log.debug("Existing CFG file is empty. "
                              "Maybe we fucked it up earlier or something? "
                              "Overwriting it.")
                    # Probably our file and we fucked it up somehow. No biggie.
                    write_cfg()
                else:
                    # Not our file!? Bizarre.
                    log.warning("Existing CFG file doesn't seem to be ours. "
                                "Not going to touch it.")
                    secho(f"Check {our_cfg_fp}. "
                          "You either need to delete or rename it.", fg="red")
                    sys.exit(1)


def restart():
    log.debug("Restarting script.")
    call(sys.executable + " " + " ".join(sys.argv))
    sys.exit(0)


def ensure_bind_bound():
    # TODO make this not a big convoluted mega function...
    configkey = config.data["cs_bind"]
    bindsnippet = f'bind {configkey} "{execsnippet}"'
    log.debug("Ensuring either config.cfg or autoexec cfg contains "
              f"'{bindsnippet}'")

    _existing_binds = existing_binds()
    if configkey in _existing_binds:
        log.debug("config.cfg already contains the right bind.")
        # Could let user optionally continue to create autoexec here
        #  even though it's not necessary?
        return
    elif _existing_binds and configkey not in _existing_binds:
        # Shouldn't happen unless user has customised cs_bind themself.
        existing_binds_s = prettylist(_existing_binds, "and", pre="", post="")
        if len(_existing_binds) > 1:
            isare = "are"
        else:
            isare = "is"
        secho(f"{existing_binds_s} {isare} already bound to exec our config..."
              f"\n...but you have cs_bind set to {configkey} for some reason.",
              fg="yellow")
        existing_binds_s = prettylist(_existing_binds, "or", pre="", post="")
        secho(f"Consider changing cs_bind to {existing_binds_s} in "
              f"{config.config_path}", fg="yellow")
        for existing_bind in _existing_binds:
            if confirm(f"Change cs_bind to {existing_bind}?", default=True):
                config.data["cs_bind"] = existing_bind
                config.generate_config()
                restart()
    elif not _existing_binds:
        log.debug(f"Couldn't find {bindsnippet} in config.cfg")

    launchstr = launch_options()
    autoexecfn = autoexec_filename(launchstr)

    # They could also add launch options and write an autoexec file
    #  themselves - but that's a bit longwinded to explain?
    failecho = lambda: secho(
        f"You need to enter...\n{bindsnippet}; host_writeconfig\n"
        "...into your CSGO console.\n",
        fg="red")

    if not autoexecfn:
        log.debug("Couldn't find any autoexec in launch options.")
        secho(
            "Steam needs to be closed in order to update the CSGO launch "
            "options. Killing it will also close any games you have running.",
            fg="red")
        if not confirm("Kill Steam.exe? [y/n]", show_default=False):
            log.debug("User decided not to kill Steam to "
                      "update launch options.")
            failecho()
            pause()
            restart()
            return

        autoexecfn = "autoexec.cfg"
        log.debug("Steam needs to be closed to update launch options. "
                  "Killing it AND ITS CHILDREN")
        call("taskkill /f /t /im steam.exe") # asking nicely just minimises steam to tray so /f is required.

        execs = f" -exec {autoexecfn}"
        launchstr += execs
        set_launch_options(launchstr)
        log.debug(f"Added '{execs}' to launch options.")

        log.debug("Opening Steam.")
        steam_exe_fp = os.path.join(steam_dir, "Steam.exe")
        Popen(steam_exe_fp)
        log.debug(f"Opened Steam. ({steam_exe_fp})")

    autoexecfp = os.path.join(cs_cfg_dir, autoexecfn)
    foundbind = False
    log.debug(f"Checking if bind is in {autoexecfn}")
    # yes this is a thing of beauty. you are right to stare.
    pattern = (f"^(?!.*?//).*?(?:(?:^|;)[ \t]*)(bind[ \t]+\"?(.+?)\"?[ \t]+\"({execsnippet}(?:.cfg)?)\"(?:[ \t]*(?:$|;)))")
    try:
        with open(autoexecfp, "r", encoding="utf8") as f:
            for line in f:
                match = re.search(pattern, line)
                if match:
                    fullbind = match.group(1)
                    bindkey = match.group(2)
                    #bindval = match.group(3)
                    if bindkey != configkey:
                        log.debug(f"Found '{fullbind}' in {autoexecfn} - "
                                  "but that won't work because "
                                  f"cs_bind is set to {configkey}")
                    else:
                        log.debug(f"{autoexecfn} already contains '{fullbind}'")
                        if game_name in list_open_windows():
                            log.debug("Game is already open.")
                            failecho()
                            pause()
                            restart()
                        else:
                            secho("The right bind is already in your autoexec! "
                                  "Everything should work "
                                  "when you open the game.", fg="green")
                        foundbind = True
    except FileNotFoundError:
        log.debug(f"Can't find bind in autoexec because {autoexecfn} "
                  "doesn't exist.")

    if not foundbind:
        add_to_autoexec(bindsnippet, autoexecfp)


def gen_GSI_cfg():
    # don't need to use jinja2 for this but may as well.
    s = render_from_file(gsi_cfg_template_fp, port=port, appname=appname)
    log.debug("GSI CFG:\n" + s)
    return s


def make_gsi_cfg():
    def write_GSI_cfg(cfg_s):
        """ cfg_s should be gen_GSI_cfg() output"""
        with open(gsi_config_fp, "w") as f:
            f.write(cfg_s)
        log.debug("Successfully wrote GSI config.")
    gsi_cfg = gen_GSI_cfg()
    # read existing GSI config first
    try:
        with open(gsi_config_fp, "r") as f:
            existing_gsi_cfg = f.read()
    except FileNotFoundError:
        # First run? Cool.
        log.debug("GSI config doesn't exist.")
        write_GSI_cfg(gsi_cfg)
        if game_name in list_open_windows():
            log.warning("CS is already running. It needs to be restarted "
                        "for it to notice the gamestate integration cfg.")
            secho("You need to restart CS for individual weapon configs "
                  "to work.", fg="red")
    else:
        if existing_gsi_cfg != gsi_cfg:
            log.debug("Old GSI CFG:\n" + existing_gsi_cfg)
            log.debug("Existing GSI config is outdated. Overwriting it. "
                      f"({gsi_config_fp})")
            if game_name in list_open_windows():
                log.warning("CS is already running. It needs to be restarted "
                            "for changes to the gamestate integration cfg "
                            "to take effect.")
                secho("You need to restart CS for individual weapon configs "
                      "to work.", fg="red")
            write_GSI_cfg(gsi_cfg)


gsi_handler = GSIPayloadHandler()

@fapp.route("/", methods=["POST"])
def GSI_post():
    gsi_handler.process(json.loads(request.data.decode("UTF-8")))
    return http_code(HTTPStatus.OK)


@lru_cache()
def http_code(status):
    assert type(status) == type(HTTPStatus.OK)
    return (status.phrase, status.value)


@fapp.before_first_request
def before_first_req():
    log.debug("Recieved our first request")


@click.command()
@click.option("--debug", is_flag=True,
              help=("Show debug messages"))
def cli(debug):
    """
    Automatically execute different CSGO cfg files depending on
    what weapon you have out.
    \n
    Example use: Have different crosshairs set up in slot1.cfg and slot2.cfg
    """
    SetConsoleTitle(appname)

    for loghandler in log.handlers:
        if isinstance(loghandler, logging.handlers.MemoryHandler):
            conhandler = loghandler.target
            if debug:
                # set flushlevel so debugs are handled when we flush in a sec
                loghandler.flushLevel = logging.DEBUG
            else:
                conhandler.setLevel(logging.INFO)
            loghandler.flush()
            # we could remove memhandler and add conhandler here BUT then
            # conhandler wouldn't be last, and strip ansi formatter doesn't work
            loghandler.capacity = 1

    make_gsi_cfg()

    ensure_bind_bound()

    # Tone down werkzeug's logging
    wlog = logging.getLogger("werkzeug")
    wlog.setLevel(logging.WARN)

    server = Thread(target=lambda: fapp.run(port=port), daemon=True)
    server.start()

    termwidth, _ = click.get_terminal_size()
    secho("Ready.".center(termwidth), fg="green")
    log.debug(f"GSI endpoint server is running on http://127.0.0.1:{port}")

    systray = tray_icon()
    try:
        systray.start()
        while systray._message_loop_thread.isAlive():
            systray._message_loop_thread.join(1)
    except KeyboardInterrupt:
        systray.shutdown()


if __name__ == "__main__":
    cli()
