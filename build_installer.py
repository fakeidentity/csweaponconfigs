import os
from subprocess import call
from urllib.request import urlretrieve
from shutil import copyfile


current_dir = os.path.dirname(os.path.realpath(__file__))
installercfg = os.path.join(current_dir, "installer.cfg")
call(f"pynsist --no-makensis {installercfg}")

build_dir = os.path.join(current_dir, r"build\nsis")

pkg_dir = os.path.join(build_dir, "pkgs")
urlretrieve("https://raw.githubusercontent.com/ActiveState/appdirs/master/LICENSE.txt",
            os.path.join(pkg_dir, "appdirs-LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/pypa/setuptools/master/LICENSE",
            os.path.join(pkg_dir, "pkg_resources", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/pallets/markupsafe/master/LICENSE",
            os.path.join(pkg_dir, "markupsafe", "LICENSE.txt"))
urlretrieve("https://raw.githubusercontent.com/pallets/markupsafe/master/AUTHORS",
            os.path.join(pkg_dir, "markupsafe", "AUTHORS.txt"))

urlretrieve("https://raw.githubusercontent.com/pallets/jinja/master/LICENSE",
            os.path.join(pkg_dir, "jinja2", "LICENSE.txt"))
urlretrieve("https://raw.githubusercontent.com/pallets/jinja/master/AUTHORS",
            os.path.join(pkg_dir, "jinja2", "AUTHORS.txt"))

urlretrieve("https://raw.githubusercontent.com/pallets/werkzeug/master/LICENSE",
            os.path.join(pkg_dir, "werkzeug", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/kmike/port-for/master/LICENSE.txt",
            os.path.join(pkg_dir, "port_for", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/pallets/flask/master/LICENSE",
            os.path.join(pkg_dir, "flask", "LICENSE.txt"))
urlretrieve("https://raw.githubusercontent.com/pallets/flask/master/AUTHORS",
            os.path.join(pkg_dir, "flask", "AUTHORS.txt"))

urlretrieve("https://raw.githubusercontent.com/tartley/colorama/master/LICENSE.txt",
            os.path.join(pkg_dir, "colorama", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/pallets/click/master/LICENSE",
            os.path.join(pkg_dir, "click", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/Infinidat/infi.systray/develop/LICENSE",
            os.path.join(pkg_dir, "infi", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/jacexh/pyautoit/master/LICENSE",
            os.path.join(pkg_dir, "autoit", "LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/mhammond/pywin32/master/Pythonwin/License.txt",
            os.path.join(pkg_dir, "pywin32-pythonwin-LICENSE.txt"))

urlretrieve("https://raw.githubusercontent.com/pallets/itsdangerous/master/LICENSE",
            os.path.join(pkg_dir, "itsdangerous-LICENSE.txt"))

copyfile(os.path.join(current_dir, "README.txt"),
         os.path.join(pkg_dir, "weaponconfigs", "README.txt"))
copyfile(os.path.join(current_dir, "LICENSE.txt"),
         os.path.join(pkg_dir, "weaponconfigs", "LICENSE.txt"))

makensis = os.path.expandvars(r"%PROGRAMFILES(x86)%\NSIS\makensis.exe")
installernsi = os.path.join(build_dir, "installer.nsi")
call(f"{makensis} {installernsi}")