# fme-packager changes

# dev

* Print output of wheel build result.
* `config-env`: don't require write access to FME_HOME folder.

# 1.16.1

* Require the `PYTHON_COMPATIBILITY` keyword only for packages where minimum build is before FME 2022. (FMEENGINE-86130)

# 1.16.0

* Add support for data processing types (FMEHUBDEV-1661)

# 1.15.1

* Fix bug where deprecated custom transformers did not set the deprecation status of the package

# 1.15.0

* Require Python >= 3.9.
* Allow wheel builds for packages that use pyproject.toml exclusively.

# 1.14.0

* Add support for optional contexts in package_help.csv (FMEENGINE-85240)

# 1.13.0

* Validate that package.yml contains unique names for content items for each type (FMEENGINE-85295)

# 1.9.0

* Add support for optional FORMAT_CATEGORIES column in format.db (Column introduced in FME b24591).

# 1.8.0

* Add formats support for summarize command.

# 1.7.3

* Fix bug in summarize command when the package does not contain any transformers

# 1.7.2

* Fix bug after removal of verbose option from summarize command

# 1.7.1

* Fix missing spec file for summarize command

# 1.7.0

* Add summarize command to show a detailed summary of the contents of an fpkg file.

# 1.6.0

* Update `fme-packager config-env` for path changes in FME 2023.2+.

# 1.5.0

* Require Python 3.7 or newer.
* Update dependencies.

# 1.4.4

* Improve help validation for packages with hyphenated UIDs.

# 1.4.3

* Improve verify command

# 1.4.2

* Improve help validation for packages containing formats.

# 1.4.0

* Added `fme-packager verify` to check that a `.fpkg` is valid.
* Moved `fme-packager version` to the standardized `fme-packager --version`.

## 1.3.1

* Fix regression in Python 3.6 and 3.7 support when processing help folder.

## 1.3.0

* Automatically generate HTML doc from Markdown files in help folder.
* Improve validation of help/package_help.csv.

## 1.2.0

* Add support for FMXJ transformers.
* Don't require Git when using `fme-packager init transformer`.

## 1.1.3

* Prepare for PyPI release.

## 1.1.0

* Add `config-env` command to configure a Python environment to use fmeobjects.

## 1.0.2

* Fix `fme-packager pack .` regression.

## 1.0.1

* Fix missing spec.json.

## 1.0.0

* Rename to fme-packager.

## 0.9.1

* Drop support for Python 2 and Python < 3.6.

## 0.8.5

* Set minimum PYTHON_COMPATIBILITY to >= '35'.

## 0.8.4

* Validate only the latest PYTHON_COMPATIBILITY value in the fmx.

## 0.8.3

* Change the transformer template URL to HTTPS.

## 0.8.2

* Correct validation for the fmx PYTHON_COMPATIBILITY parameter to be >= '36'.
* Correct validation error messages related to PYTHON_COMPATIBILITY.

## 0.8.1

* Update transformer cookiecutter template URL.
* Remove pda_pipeline cookiecutter template. Used for internal purposes only.

## 0.8.0

* Add validation on PYTHON_COMPATIBILITY parameter in transformer fmx to be >= 3.6

## 0.7.0

* Add `fme-packager apply-help [help_path] [fpkg_path]` command to import doc from Safe TechPubs
  into an FME Package repository.
* Update `fme-packager pack` to include contents of `help/`, with basic validation.

## 0.6.3

* Reorder MARKETING_FAMILY column in formatinfo definition.

## 0.6.2

* Add MARKETING_FAMILY column validation for formatinfo.

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
