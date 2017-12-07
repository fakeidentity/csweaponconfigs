#import os
import site
#scriptdir, script = os.path.split(__file__)
#pkgdir = os.path.join(scriptdir, "pkgs")
# so .pth files in /pkgs are picked up
site.addsitedir(pkgdir)