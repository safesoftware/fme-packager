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
def fmxj_package_dir():
    return os.path.join(FIXTURES_DIR, "fmxj_package")


@pytest.fixture
def incompatible_custom_package_dir():
    return os.path.join(FIXTURES_DIR, "incompatible_custom_package")


@pytest.fixture
def data_processing_types_package_dir():
    return os.path.join(FIXTURES_DIR, "data_processing_types")


@pytest.fixture
def mock_transformer(mocker):
    mock_transformer = mocker.Mock()
    mock_transformer.name = "MyTransformer"
    mock_transformer.version = "1.0.0"
    mock_transformer.categories = ["Category1", "Category2"]
    mock_transformer.aliases = ["Alias1", "Alias2"]
    mock_transformer.visible = True
    return mock_transformer


@pytest.fixture
def mock_transformer_file(mocker, mock_transformer):
    # Mock the TransformerFile object
    mock_transformer_file = mocker.Mock()

    # Mock the versions method to return a list of mock Transformer objects
    mock_transformer_file.versions.return_value = [mock_transformer]

    return mock_transformer_file
