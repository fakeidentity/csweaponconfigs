import sys
import os
import glob
import re
from fileinput import FileInput
#from subprocess import Popen, call

from win32gui import (GetWindowText, GetForegroundWindow, EnumWindows,
                      IsWindowVisible)
import vdf
#from click import secho, confirm

from log import getLogger, modulename

log = getLogger(modulename())

steam_dir = os.path.expandvars(r"%PROGRAMFILES(x86)%\Steam")
cs_cfg_dir = os.path.join(steam_dir, "steamapps\common\Counter-Strike Global Offensive\csgo\cfg")
our_cfg_fn = "weapon_configs.cfg"
our_cfg_fp = os.path.join(cs_cfg_dir, our_cfg_fn)
execsnippet = "exec {}".format(our_cfg_fn.rpartition(".")[0])

def active_window_title():
    return GetWindowText(GetForegroundWindow())


def list_open_windows():
    titles = []
    def enum_func(hwnd, _):
        if IsWindowVisible(hwnd):
            title = GetWindowText(hwnd)
            if title:
                titles.append(title)
    EnumWindows(enum_func, 0)
    return titles


# https://www.autoitscript.com/autoit3/docs/appendix/SendKeys.htm
cs_bind_autoit_map = {
    "F1": "{F1}", "F2": "{F2}", "F3": "{F3}", "F4": "{F4}", "F5": "{F5}", "F6": "{F6}", "F7": "{F7}", "F8": "{F8}", "F9": "{F8}", "F10": "{F10}", "F11": "{F11}", "F12": "{F12}", "SCROLLLOCK": "{SCROLLLOCK}", "Pause": "{PAUSE}",
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",  "0": "0", "-": "-", "=": "=", "Backspace": "{BACKSPACE}",
    "Tab": "{TAB}", "Q": "Q", "W": "W", "E": "E", "R": "R", "T": "T", "Y": "Y", "U": "U", "I": "I", "O": "O", "P": "P", "[": "[", "]": "]", "\\": "\\",
    "CapsLock": "{CAPSLOCK}", "A": "A", "S": "S", "D": "D", "F": "F", "G": "G", "H": "H", "J": "J", "K": "K", "L": "L", "Semicolon": ";", "'": "'", "Enter": "{ENTER}",
    "Shift": "{LSHIFT}", "Z": "Z", "X": "X", "C": "C", "V": "V", "B": "B", "N": "N", "M": "M", ",": ",", ".": ".", "/": "/", "RShift": "{RSHIFT}",
    "Ctrl": "{LCTRL}", "Alt": "{LALT}", "Space": "{SPACE}", "RAlt": "{RALT}", "RCtrl": "{RCTRL}",
    "Ins": "{INSERT}", "Home": "{HOME}", "PgUp": "{PGUP}", "Del": "{DELETE}", "End": "{END}", "PgDn": "{PGDN}",
    "UpArrow": "{UP}", "LeftArrow": "{LEFT}", "DownArrow": "{DOWN}", "RightArrow": "{RIGHT}",
    "NumLock": "{NUMLOCK}", "KP_SLASH": "{NUMPADDIV}", "KP_MULTIPLY": "{NUMPADMULT}", "KP_MINUS": "{NUMPADSUB}",
    "KP_HOME": "{NUMPAD7}", "KP_UPARROW": "{NUMPAD8}", "KP_PGUP": "{NUMPAD9}",
    "KP_LEFTARROW": "{NUMPAD4}", "KP_5": "{NUMPAD5}", "KP_RIGHTARROW": "{NUMPAD6}", "KP_PLUS": "{NUMPADADD}",
    "KP_END": "{NUMPAD1}", "KP_DOWNARROW": "{NUMPAD2}", "KP_PGDN": "{NUMPAD3}",
    "KP_INS": "{NUMPAD0}", "KP_DEL": "{NUMPADDOT}", "KP_ENTER": "{NUMPADENTER}"
}
cs_bindnames = {k.upper() for k in cs_bind_autoit_map.keys()}


def bind_data():
    log.debug("Looking up bind data.")
    userdata_glob = r"%PROGRAMFILES(x86)%\Steam\userdata\*\730\local\cfg\*.cfg"
    userdata_cfgs = glob.glob(os.path.expandvars(userdata_glob))
    from collections import defaultdict
    binds = defaultdict(list)
    for fp in userdata_cfgs:
        with open(fp, "r") as f:
            for line in f:
                match = re.match(r"bind \"(.+?)\" \"(.+?)\"", line)
                if match:
                    keyname = match.group(1).upper()
                    bindval = match.group(2)
                    #if keyname in binds and binds[keyname][0] != bindval:
                        #log.debug(f"{keyname} already in binds.")
                        #log.debug(f"old: bind {keyname} \"{binds[keyname][0]}\"")
                        #log.debug(f"new: bind {keyname} \"{bindval}\"")
                    if keyname in binds and binds[keyname][0] == bindval:
                        continue
                    binds[keyname].append(bindval)
    return binds


def used_binds(data=None):
    if not data:
        data = bind_data()
    return data.keys()


def unused_binds(data=None):
    if not data:
        data = bind_data()
    return cs_bindnames.difference(used_binds(data))


localconfig_glob = r"%PROGRAMFILES(x86)%\Steam\userdata\*\config\localconfig.vdf"

def localconfig_fp():
    localconfigs = glob.glob(os.path.expandvars(localconfig_glob))
    return sorted(localconfigs, key=os.path.getmtime, reverse=True)[0]


def localconfig_data():
    localconfigs = glob.glob(os.path.expandvars(localconfig_glob))
    launchparams = []
    with open(localconfig_fp(), "r", encoding="utf8") as f:
        return vdf.load(f)


def launch_options():
    log.debug("Reading CSGO launch options.")
    data = localconfig_data()
    return data["UserLocalConfigStore"]["Software"]["Valve"] \
                        ["Steam"]["Apps"]["730"]["LaunchOptions"]


def autoexec_filename(launchstr=""):
    log.debug("Determining autoexec filenames from CSGO launch options.")
    if not launchstr:
        launchstr = launch_options()
    match = re.search(r"[+-]exec (\w+)(?:\.cfg)?", launchstr)
    if match:
        log.debug(f"Found '{match.group(0)}' in launch options.")
        cfg = match.group(1)
        cfg += ".cfg"
        return cfg


def existing_binds(binddata=None):
    if not binddata:
        binddata = bind_data()
    binds = [k for k, v in binddata.items() if execsnippet in v]
    if binds:
        for key in binds:
            log.debug(f"{key} is already bound to '{execsnippet}'.")
        return binds


def prettylist(list_, conjunc, pre="'", post="'"):
    """
    Takes a list and returns a basic human-readable string listing the elements.
    eg.
    >>> prettylist([1, 2], conjunc="and")
    "'1' and '2'"

    >>> prettylist([1, 2, 3], conjunc="or")
    "'1', '2', or '3'"
    """
    if not list_:
        raise ValueError
    list_ = [f"{pre}{x}{post}" for x in list_]
    if len(list_) > 1:
        s1 = ", ".join(list_[:-1])
        s2 = list_[-1]
        if len(list_) == 2:
            s = f"{s1} {conjunc} {s2}"
        else:
            s = f"{s1}, {conjunc} {s2}"
    else:
        s = list_[0]
    return s


def add_to_autoexec(s, autoexecfp=None):
    if not autoexecfp:
        autoexecfp = os.path.join(cs_cfg_dir,
                                  autoexec_filename() or "autoexec.cfg")
    autoexecfn = os.path.basename(autoexecfp)

    if not os.path.isfile(autoexecfp):
        log.debug(f"autoexec file doesn't exist. Creating it. ({autoexecfp})")
        with open(autoexecfp, "w", encoding="utf8") as f:
            f.write("host_writeconfig "
                    "// this is required and needs to be at the end.")

    log.debug(f"Adding string to bottom of {autoexecfn}:\n{s}")
    with FileInput(autoexecfp, inplace=True) as f:
        for line in f:
            print(re.sub(r"(host_writeconfig\s*;?)",
                         rf'{s}\n\n\1',
                         line),
                  end="")


#def ensure_bind_bound():
    ## TODO make this not a big convoluted mega function...
    ## why is this in utils anyway? coz SHUTUP, IS WHY
    #configkey = config.data["cs_bind"]
    #bindsnippet = f'bind {configkey} "{execsnippet}"'
    #log.debug("Ensuring either config.cfg or autoexec cfg contains "
              #f"'{bindsnippet}'")

    #_existing_binds = existing_binds()
    #if configkey in _existing_binds:
        #log.debug("config.cfg already contains the right bind.")
        ## Could let user optionally continue to create autoexec here
        ##  even though it's not necessary?
        #return
    #elif _existing_binds and configkey not in _existing_binds:
        ## Shouldn't happen unless user has customised cs_bind themself.
        #existing_binds_s = prettylist(_existing_binds, "and", pre="", post="")
        #if len(_existing_binds) > 1:
            #isare = "are"
        #else:
            #isare = "is"
        #secho(f"{existing_binds_s} {isare} already bound to exec our config..."
              #f"\n...but you have cs_bind set to {configkey} for some reason.",
              #fg="yellow")
        #existing_binds_s = prettylist(_existing_binds, "or", pre="", post="")
        #secho(f"Consider changing cs_bind to {existing_binds_s} in "
              #f"{config.config_path}", fg="yellow")
        #for existing_bind in _existing_binds:
            #if confirm(f"Change cs_bind to {existing_bind}?", default=True):
                #config.data["cs_bind"] = existing_bind
                #config.generate_config()
                #log.debug("Restarting script.")
                #call(sys.executable + " " + " ".join(sys.argv))
                #sys.exit(0)
    #elif not _existing_binds:
        #log.debug(f"Couldn't find {bindsnippet} in config.cfg")

    #launchstr = launch_options()
    #autoexecfn = autoexec_filename(launchstr)

    #if not autoexecfn:
        #log.debug("Couldn't find any autoexec in launch options.")
        #secho(
            #"Steam needs to be closed in order to update the CSGO launch "
            #"options. Killing it will also close any games you have running.",
            #fg="red")
        #if not confirm("Kill Steam.exe? [y/n]", show_default=False):
            #log.debug("User decided not to kill Steam.")
            ## They could also add launch options and write an autoexec file
            ##  themselves - but that's a bit longwinded to explain?.
            #secho(
                #f"You need to enter...\n{bindsnippet}; host_writeconfig\n"
                #"...into your CSGO console.\n",
                #fg="red")
            #sys.exit(1)
            #return

        #autoexecfn = "autoexec.cfg"
        #log.debug("Steam needs to be closed to update launch options. "
                  #"Killing it AND ITS CHILDREN")
        #os.system("taskkill /f /t /im steam.exe") # asking nicely just minimises steam to tray so /f is required.

        #execs = f" -exec {autoexecfn}"
        #data = localconfig_data()
        #data["UserLocalConfigStore"]["Software"]["Valve"] \
            #["Steam"]["Apps"]["730"]["LaunchOptions"] += execs
        #with open(localconfig_fp(), "w", encoding="utf8") as f:
            #vdf.dump(data, f, pretty=True)
        #log.debug(f"Added '{execs}' to launch options.")

        #log.debug("Opening Steam.")
        #steam_exe_fp = os.path.join(steam_dir, "Steam.exe")
        #Popen(steam_exe_fp)
        #log.debug(f"Opened Steam. ({steam_exe_fp})")

    #autoexecfp = os.path.join(cs_cfg_dir, autoexecfn)
    #foundbind = False
    #log.debug(f"Checking if bind is in {autoexecfn}")
    ## yes this is a thing of beauty. you are right to stare.
    #pattern = (f"^(?!.*?//).*?(?:(?:^|;)[ \t]*)(bind[ \t]+\"?(.+?)\"?[ \t]+\"({execsnippet}(?:.cfg)?)\"(?:[ \t]*(?:$|;)))")
    #try:
        #with open(autoexecfp, "r", encoding="utf8") as f:
            #for line in f:
                #match = re.search(pattern, line)
                #if match:
                    #fullbind = match.group(1)
                    #bindkey = match.group(2)
                    #bindval = match.group(3)
                    #if bindkey != configkey:
                        #log.debug(f"Found '{fullbind}' in {autoexecfn} - "
                                  #"but that won't work because "
                                  #f"cs_bind is set to {configkey}")
                    #else:
                        #log.debug(f"{autoexecfn} already contains '{fullbind}'")
                        #foundbind = True
    #except FileNotFoundError:
        #log.debug(f"Can't find bind in autoexec because {autoexecfn} "
                  #"doesn't exist.")

    #if not foundbind:
        #add_to_autoexec(bindsnippet, autoexecfp)


import config # TODO resolve this circular import some other way