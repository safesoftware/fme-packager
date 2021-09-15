import os

import pytest

from fpkgr.exception import PythonCompatibilityError
from fpkgr.packager import FMEPackager, check_fmx, is_valid_python_compatibility


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


def test_check_fmx(valid_package_dir):
    packager = FMEPackager(valid_package_dir)
    for transformer in packager.metadata.transformers:
        src = os.path.join(valid_package_dir, 'transformers')
        fmx_path = os.path.join(src, "{}.fmx".format(transformer.name))
        check_fmx(packager.metadata, transformer, fmx_path)


def test_check_fmx_with_compatibility_error(incompatible_package_dir):
    packager = FMEPackager(incompatible_package_dir)
    for transformer in packager.metadata.transformers:
        src = os.path.join(incompatible_package_dir, 'transformers')
        fmx_path = os.path.join(src, "{}.fmx".format(transformer.name))

        with pytest.raises(PythonCompatibilityError):
            check_fmx(packager.metadata, transformer, fmx_path)
