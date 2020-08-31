# fpkgr changes

## 0.6.1

* Update dependencies

## 0.6.0

* Exclude .DS_Store, Thumbs.db, and desktop.ini from fpkg.
* Avoid creating empty `python` directory in fpkg.

## 0.5.0

* Handle `bdist_wheel` creating wheels with filenames that replace `-`
  in the Python package name with `_`.
* Delete `python/*/dist/` directories as part of Python wheel building.
* Enable support for formats.

## 0.4.0

* Support inclusion of localization files.
  They were added to the fpkg specification on 2018-10-26.

## 0.3.1

* Support Custom Transformers in UTF-8.


## 0.3.0

* Support Custom Transformers, with extra validations specific to them.
* Fix crash when there's no Python directory to package.


## 0.2.0

* Add `version` command to show version of this tool.
* Fix inclusion of Web Service and Web Filesystem definitions.
