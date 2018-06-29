# fpkgr: FME Package Creator

`fpkgr` is a Python command-line tool for validating and creating FME Packages.
Give it the path to an FME Package directory, and it'll do some quick checks
and build an `.fpkg` file out of it.

The validations done by `fpkgr` will catch common mistakes in package development,
but is still very basic. The FME Packages it creates will be
validly formed according to the FME Packages Specification,
but whether the installed components function correctly within FME is not in its scope.


## Install

Download the latest whl distribution from the releases page. Then install it:

```
$ pip install [fpkgr].whl
```

Once installed, the `fpkgr` command is available on your system.
`fpkgr --help` shows an overview of commands.


## What it does

* Validate package.yml against the FME Packages Specification.
* Verifies that components listed in package.yml are present.
* Checks that transformer and version names are correct.
* Verifies that the transformer version in the package.yml is
  included in the FMX.
* Excludes components that are present in directories,
  but not listed in package.yml.
* Cleans and rebuilds wheels for Python packages that are subdirectories of `python/`.
* Copies wheels from `python/*/dist` into `python/`.
* Enforces required package icon dimensions.

These steps are done while copying files into a temporary build directory,
so existing files are not modified. 


## Make an fpkg distribution

Call `fpkgr pack` with the path to your package directory (it contains package.yml):

```
$ fpkgr pack my-package
```

If everything went well, the fpkg will be in `my-package/dist/`.
