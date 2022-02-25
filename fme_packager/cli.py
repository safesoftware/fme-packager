"""
fme_packager command line interface.
"""
import inspect
import os
import shutil
import sys
import sysconfig
from pathlib import Path

import click
from cookiecutter.main import cookiecutter

import fme_packager
from fme_packager.packager import FMEPackager


@click.group()
def cli():
    """
    fme_packager: The FME Packages Tool.
    """
    pass


COOKIECUTTER_TEMPLATES = {
    "transformer": "https://github.com/safesoftware/fpkg-transformer-template.git",
}


@cli.command()
@click.argument("template", type=click.Choice(sorted(COOKIECUTTER_TEMPLATES.keys())))
def init(template):
    """
    Initialize an FME Package from a template.

    The template is initialized in a subdirectory of the current directory.

    TEMPLATE -- Name of the template to use.
    """
    print("Enter the values to use for the template. Press Enter to accept the [default].")
    cookiecutter(COOKIECUTTER_TEMPLATES[template])


@cli.command()
@click.argument("help_path", type=click.Path(exists=True, file_okay=True))
@click.argument("fpkg_path", type=click.Path(exists=True, file_okay=False, writable=True))
def apply_help(help_path, fpkg_path):
    """
    Import an Safe TechPubs doc export into an FME Package directory.

    This operation also converts package_aliases.flali to package_help.csv at the destination.

    HELP_PATH -- Path to a ZIP or directory of an Safe TechPubs doc export. Read only.

    FPKG_PATH -- Path to the FME Package root. Its 'help' subdirectory will be recreated.
    """
    steps = FMEPackager(fpkg_path)
    steps.apply_help(help_path)


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, writable=True))
def pack(path):
    """
    Create an .fpkg file.

    Package contents are validated during this process.
    Components not referenced by the package's metadata.yml may not be included in the resulting fpkg.

    PATH -- Path to an FME Package directory.
    """
    steps = FMEPackager(path)
    steps.build()
    steps.make_fpkg()


@cli.command()
@click.option(
    "--fme-home",
    prompt=True,
    default=lambda: os.environ.get("FME_HOME"),
    show_default="FME_HOME environment variable",
    type=click.Path(exists=True, file_okay=False, writable=True),
    required=True,
    help="Path to FME installation",
)
@click.option(
    "--site-packages-dir",
    default=lambda: sysconfig.get_paths()["purelib"],
    show_default="current Python environment",
    type=click.Path(exists=True, file_okay=False, writable=True),
    required=True,
    help="Path to Python environment's site-packages",
)
def config_env(fme_home, site_packages_dir):
    """
    Configure a Python environment for access to fmeobjects
    and the Python libraries included with FME.
    """
    leaf_dir = "python%s%s" % (sys.version_info.major, sys.version_info.minor)
    paths_to_add = [
        "#" + fme_home,
        os.path.join(fme_home, "python"),
        os.path.join(fme_home, "python", leaf_dir),
        os.path.join(fme_home, "fmeobjects", leaf_dir),
    ]

    dst_pth = os.path.join(site_packages_dir, "fme_env.pth")
    print("Writing " + dst_pth)
    with open(dst_pth, "w") as f:
        for path in paths_to_add:
            f.write(path + "\n")
        f.write("import fme_env\n")

    dst_py = os.path.join(site_packages_dir, "fme_env.py")
    print("Writing " + dst_py)
    src = Path(inspect.getfile(fme_packager)).parent / "fme_env.py"
    shutil.copy(src, dst_py)

    print("\nThis Python environment is now set up for access to FME and fmeobjects.")
    print("If the FME install location changes, re-run this script to update paths.")


@cli.command()
def version():
    """
    Print the version of fme_packager.
    """
    print("fme_packager " + fme_packager.__version__)


if __name__ == "__main__":
    cli()
