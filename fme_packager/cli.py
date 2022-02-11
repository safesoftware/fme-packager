"""
fme_packager command line interface.
"""
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
def version():
    """
    Print the version of fme_packager.
    """
    print("fme_packager " + fme_packager.__version__)


if __name__ == "__main__":
    cli()
