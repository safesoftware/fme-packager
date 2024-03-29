# coding: utf-8
from __future__ import print_function, unicode_literals, absolute_import, division

import os
import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent.resolve() / "fixtures"


@pytest.fixture
def valid_package_dir():
    return os.path.join(FIXTURES_DIR, "valid_package")


@pytest.fixture
def incompatible_package_dir():
    return os.path.join(FIXTURES_DIR, "incompatible_package")


@pytest.fixture
def custom_package_dir():
    return os.path.join(FIXTURES_DIR, "custom_package")


@pytest.fixture
def incompatible_custom_package_dir():
    return os.path.join(FIXTURES_DIR, "incompatible_custom_package")
