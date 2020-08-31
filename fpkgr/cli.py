"""
fpkgr command line interface
"""
import click
from cookiecutter.main import cookiecutter

import fpkgr
from fpkgr.packager import FMEPackager


@click.group()
def cli():
    """
    fpkgr: The FME Packages Tool
    """
    pass


COOKIECUTTER_TEMPLATES = {
    "transformer": "git@gtb-1.base.safe.com:Safe/fpkg-transformer-template.git",
    "pda_pipeline": "git@gtb-1.base.safe.com:Safe/fpkg-pipeline-template.git",
}


@cli.command()
@click.argument('template', type=click.Choice(sorted(COOKIECUTTER_TEMPLATES.keys())))
def init(template):
    """
    Initialize an FME Package from a template.

    The template is initialized in a subdirectory of the current directory.

    TEMPLATE -- name of the template to use.
    """
    print("Enter the values to use for the template. Press Enter to accept the [default].")
    cookiecutter(COOKIECUTTER_TEMPLATES[template])


@cli.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False, writable=True))
def pack(path):
    """
    Create an .fpkg file.

    Package contents are validated during this process.
    Components not referenced by the package's metadata.yml may not be included in the resulting fpkg.

    path -- Path to an FME Package directory.
    """
    steps = FMEPackager(path)
    steps.build()
    steps.make_fpkg()


@cli.command()
def version():
    """
    Print the version of fpkgr.
    """
    print('fpkgr ' + fpkgr.__version__)


if __name__ == "__main__":
    cli()
