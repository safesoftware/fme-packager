"""
fpkgr command line interface
"""
import click
from cookiecutter.main import cookiecutter

from fpkgr.packager import FMEPackager


@click.group()
def cli():
    """
    fpkgr: The FME Packages Tool
    """
    pass


COOKIECUTTER_TEMPLATES = {
    'transformer': 'http://gtb-1.safe.internal/clam/fpkg-transformer-template.git',
}


@cli.command()
@click.argument('template', type=click.Choice(['transformer']))
def init(template):
    """
    Initialize an FME Package from a template.

    The template is initialized in a subdirectory of the current directory.

    template -- name of the template to use
    """
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


if __name__ == "__main__":
    cli()
