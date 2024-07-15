"""
Add FME_HOME to the Windows DLL search path or OS library load path.

See `fme-packager config-env` for details.
"""

import os
import sysconfig


# First line from fme_env.pth is FME_HOME
site_packages_dir = sysconfig.get_paths()["purelib"]
src_pth = os.path.join(site_packages_dir, "fme_env.pth")
with open(src_pth, "r") as f:
    fme_home = f.readline().strip("#\n ")

if fme_home:
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(fme_home)
    else:
        os.environ["PATH"] = fme_home + ";" + os.environ["PATH"]
