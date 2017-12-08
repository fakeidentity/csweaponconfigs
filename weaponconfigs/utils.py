import os
import glob
import re
from fileinput import FileInput
from collections import defaultdict

from win32gui import (GetWindowText, GetForegroundWindow, EnumWindows,
                      IsWindowVisible, ShowWindow)
from infi.systray import SysTrayIcon
from win32console import GetConsoleWindow
import win32con

from weaponconfigs.log import getLogger, modulename
from weaponconfigs.__init__ import appname, data_dir

log = getLogger(modulename())

steam_dir = os.path.expandvars(r"%PROGRAMFILES(x86)%\Steam")
cs_cfg_dir = os.path.join(steam_dir, r"steamapps\common\Counter-Strike Global Offensive\csgo\cfg")
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


def bind_data(current_only=False):
    log.debug("Looking up bind data.")
    userdata_glob = r"%PROGRAMFILES(x86)%\Steam\userdata\*\730\local\cfg\*.cfg"
    userdata_cfgs = glob.glob(os.path.expandvars(userdata_glob))
    userdata_cfgs = sorted(userdata_cfgs, key=os.path.getmtime, reverse=True)
    binds = defaultdict(list)
    bindpattern = re.compile(r"bind \"(.+?)\" \"(.+?)\"")
    for fp in userdata_cfgs:
        with open(fp, "r") as f:
            for line in f:
                match = bindpattern.match(line)
                if match:
                    keyname = match.group(1).upper()
                    bindval = match.group(2)
                    if keyname in binds and binds[keyname][0] == bindval:
                        continue
                    binds[keyname].append(bindval)
                if current_only:
                    break
    return binds


def used_binds(data=None):
    if not data:
        data = bind_data()
    return data.keys()


def unused_binds(data=None):
    if not data:
        data = bind_data()
    return cs_bindnames.difference(used_binds(data))


def existing_binds(binddata=None, *args, **kwargs):
    if not binddata:
        binddata = bind_data(*args, **kwargs)
    binds = [k for k, v in binddata.items() if execsnippet in v]
    if binds:
        for key in binds:
            log.debug(f"{key} is already bound to '{execsnippet}'.")
        return binds
    return []


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


def add_to_autoexec(s):
    autoexecfn = os.path.basename("autoexec.cfg")
    autoexecfp = os.path.join(cs_cfg_dir, autoexecfn)

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


class ConsoleVisibility(object):
    def __init__(self):
        self.visible = True
        self.win = GetConsoleWindow()


    def toggle_hide(self):
        self.visible = not self.visible
        ShowWindow(self.win, self.visible)


    def hide(self):
        ShowWindow(self.win, win32con.SW_HIDE)


    def minimise(self):
        ShowWindow(self.win, win32con.SW_MINIMIZE)



convis = ConsoleVisibility()

def tray_icon():
    menu = (("Show/Hide", None, lambda x: convis.toggle_hide()),)
    iconfp = os.path.join(data_dir, "icon.ico")
    systray = SysTrayIcon(iconfp, appname, menu, default_menu_index=0)
    return systray
