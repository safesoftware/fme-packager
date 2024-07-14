# fme-packager: FME Package Creator

`fme-packager` is a Python command-line tool for validating and creating FME Packages.
Give it the path to an FME Package directory, and it'll do some quick checks
and build an `.fpkg` file out of it.

The validations done by `fme-packager` will catch common mistakes in package development,
but is still very basic. The FME Packages it creates will be
validly formed according to the FME Packages Specification,
but whether the installed components function correctly within FME is not in its scope.


## Install

Download the latest whl distribution from the releases page. Then install it:

```
$ pip install [fme-packager].whl
```

Once installed, the `fme-packager` command is available on your system.
`fme-packager --help` shows an overview of commands.


## What it does

* Validate package.yml against the FME Packages Specification.
* Verifies that components listed in package.yml are present.
* Checks that transformer and format names are valid and well-formed.
* Verifies that the transformer version in the package.yml is
  included in the FMX.
* Requires that Custom Transformers be Linked Always, declare Python 3 support,
  and authored with a sufficiently recent version of FME Workbench.
* Excludes components that are present in directories,
  but not listed in package.yml.
* Cleans and rebuilds wheels for Python packages that are subdirectories of `python/`.
* Copies wheels from `python/*/dist` into `python/`.
* Enforces required package icon dimensions.

These steps are done while copying files into a temporary build directory,
so existing files are not modified.


## Get started with a template

`fme-packager init [template name]` helps you get started with developing FME Packages by
using [Cookiecutter](https://cookiecutter.readthedocs.io/) templates.

Available templates:

* `transformer`: [Transformer template for FME Packages](https://github.com/safesoftware/fpkg-transformer-template)

_These templates are not currently bundled with fme-packager._


## Make an fpkg distribution

Call `fme-packager pack` with the path to your package directory (it contains package.yml):

```
$ fme-packager pack my-package
```

If everything went well, the fpkg will be in `my-package/dist/`.

## Development Setup and Testing

To set up a development environment, clone this repository and install the dependencies:

```
$ pip install ".[dev]"
```

To run the tests:

```
$ pytest
```
