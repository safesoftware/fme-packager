"""
fme_packager command line interface.
"""

import inspect
import json as json_lib
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import click
from click import BadParameter
from cookiecutter.main import cookiecutter

import fme_packager
from fme_packager.packager import FMEPackager
from fme_packager.summarizer import summarize_fpkg
from fme_packager.verifier import FMEVerifier


@click.group()
@click.version_option(package_name="fme_packager")
def cli():
    """
    fme_packager: The FME Packages Tool.
    """
    pass


COOKIECUTTER_TEMPLATES = {
    "transformer": "https://github.com/safesoftware/fpkg-transformer-template/archive/refs/heads/main.zip",
}


@cli.command()
@click.argument("template", type=click.Choice(sorted(COOKIECUTTER_TEMPLATES.keys())))
def init(template):
    """
    Initialize a FME Package from a template.

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
    Import a Safe TechPubs doc export into an FME Package directory.

    This operation also converts package_aliases.flali to package_help.csv at the destination.

    HELP_PATH -- Path to a ZIP or directory of a Safe TechPubs doc export. Read only.

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
@click.argument("file", type=click.Path(exists=False))
@click.option("--verbose", "-v", is_flag=True, help="Show build steps")
@click.option("--json", is_flag=True, help="Output result as JSON")
def verify(file, verbose, json):
    """
    Verify that a .fpkg file is valid.

    Package contents are validated during this process.

    FILE -- Path to an FME .fpkg package file.
    """
    verifier = FMEVerifier(file, verbose, json)
    result = verifier.verify()
    print(result)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def summarize(file):
    """
    Extract a JSON representation of an .fpkg file.

    FILE -- Path to an FME .fpkg package file.
    """
    result = summarize_fpkg(file)
    print(json_lib.dumps(result, indent=2))


@cli.command()
@click.option(
    "--fme-home",
    prompt=True,
    default=lambda: os.environ.get("FME_HOME"),
    show_default="FME_HOME environment variable",
    type=click.Path(exists=True, file_okay=False, writable=False),
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
    fme_home = Path(fme_home)
    if not (fme_home / "fme").is_file() and not (fme_home / "fme.exe").is_file():
        raise BadParameter(f"'{fme_home}' does not contain an FME executable")

    leaf_dir = "python%s%s" % (sys.version_info.major, sys.version_info.minor)
    paths_to_add = [
        "#" + fme_home.as_posix(),  # fme_env.py reads this line
        (fme_home / "python").as_posix(),  # fmeobjects API and third-party libraries
        (fme_home / "python" / leaf_dir).as_posix(),  # third-party binary libraries
    ]

    # Internal libraries bundle on Windows since FME 2023.2 (FMEENGINE-78545)
    # Mac/Linux since FME 2025.1 (FOUNDATION-22)
    internal_libs_zip = (
        fme_home / "python" / f"fme-plugins-py{sys.version_info.major}{sys.version_info.minor}.zip"
    )
    if internal_libs_zip.is_file():
        paths_to_add.append(internal_libs_zip.as_posix())

    # Location of fmeobjects before FME 2023.2 (FMEENGINE-78545)
    legacy_fmeobjects_path = fme_home / "fmeobjects" / leaf_dir
    if legacy_fmeobjects_path.is_dir():
        paths_to_add.append(legacy_fmeobjects_path.as_posix())

    site_packages_dir = Path(site_packages_dir)
    dst_pth = site_packages_dir / "fme_env.pth"
    print(f"Writing {dst_pth}")
    with dst_pth.open("w") as f:
        for path in paths_to_add:
            f.write(path + "\n")
        f.write("import fme_env\n")

    dst_py = site_packages_dir / "fme_env.py"
    print(f"Writing {dst_py}")
    src = Path(inspect.getfile(fme_packager)).parent / "fme_env.py"
    shutil.copy(src, dst_py)

    print("Verifying access to fmeobjects...")
    for test_import in [
        "from fmeobjects import FMEFeature",
        "import pluginbuilder",
        "import fmewebservices",
    ]:
        try:
            subprocess.run(
                [sys.executable, "-c", f"import sys;sys.tracebacklimit=0;{test_import}"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"{test_import}: {e.stderr.decode().strip()}")
            print("Environment configuration failed.")
            sys.exit(1)
    else:
        print("\nThis Python environment is now set up for access to fmeobjects.")
        print("If the FME install location changes, re-run this script to update paths.")


if __name__ == "__main__":
    cli()
