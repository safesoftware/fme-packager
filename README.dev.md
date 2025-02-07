# Notes for fme-packager contributors

Clone this repository, then make an editable installation with development dependencies:

```
pip install -e .[dev]
```

We use Ruff to enforce code formatting and code checks.

## Tests

Run tests using `pytest` or `tox`.
Tox is configured to test all supported versions of Python when available.
It's also the entry point for CIB steps on GitHub and Jenkins.

## Releases

Production releases to PyPI are triggered by creating a release at
https://github.com/safesoftware/fme-packager/releases.
This triggers steps to build and publish the package to PyPI via the Trusted Publishing method.
