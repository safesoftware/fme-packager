"""
Add FME_HOME to the Windows DLL search path or OS library load path.

See `fme-packager config-env` for details.
"""

import os
import site
import sysconfig

# First line from fme_env.pth is FME_HOME
site_packages_dir = sysconfig.get_paths()["purelib"]
src_pth = os.path.join(site_packages_dir, "fme_env.pth")
with open(src_pth, "r") as f:
    fme_home = f.readline().strip("#\n ")

if fme_home:
    site.addsitedir(os.path.join(fme_home, "python"))  # to follow .pth files there
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(fme_home)
    os.environ["PATH"] = ";".join([fme_home, os.environ.get("PATH", "")])
