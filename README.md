# fpkgr: FME Package Creator

`fpkgr` is a Python command-line tool for validating and creating FME Packages.
Give it the path to an FME Package directory, and it'll do some quick checks
and build an `.fpkg` file out of it.

The validations done by `fpkgr` will catch common mistakes in package development,
but is not intended to be comprehensive. The FME Packages it creates will be
validly formed according to the FME Packages Specification.
Whether the installed components function correctly within FME is not in its scope.


## Install

Download the latest whl distribution from the releases page. Then install it:

```
$ pip install [fpkgr].whl
```

Once installed, the `fpkgr` command is available on your system.
`fpkgr --help` shows an overview of commands.
