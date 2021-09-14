import os

import pytest

from fpkgr.packager import is_valid_python_compatibility


@pytest.mark.parametrize("version, expected_validation", [
    ("26", False),
    ("2.6", False),
    ("27", False),
    ("ArcGISDesktop", False),
    ("36", True),
    ("37", True),
    ("3.8.9", True),
])
def test_is_valid_python_compatibility(version, expected_validation):
    assert is_valid_python_compatibility(version) == expected_validation
