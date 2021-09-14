# coding: utf-8
from __future__ import print_function, unicode_literals, absolute_import, division

import os

import pytest

FIXTURES_DIR = os.path.join(os.getcwd(), "fixtures")


@pytest.fixture
def valid_package_dir():
    return os.path.join(FIXTURES_DIR, 'valid_package')


@pytest.fixture
def incompatible_package_dir():
    return os.path.join(FIXTURES_DIR, 'incompatible_package')
