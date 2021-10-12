import os

import pytest

from fpkgr.exception import (
    TransformerPythonCompatError,
    CustomTransformerPythonCompatError,
)
from fpkgr.packager import (
    FMEPackager,
    check_fmx,
    is_valid_python_compatibility,
    check_custom_fmx,
)


def get_fmx_path(transformer_dir, transformer_name):
    return os.path.join(transformer_dir, "{}.fmx".format(transformer_name))


@pytest.mark.parametrize(
    "version, expected_is_valid",
    [
        ("26", False),
        ("27", False),
        ("ArcGISDesktop", False),
        ("35", False),
        ("36", True),
        ("37", True),
        ("3.8.9", False),  # 3.x.x is invalid version syntax for PYTHON_COMPATIBILITY
        ("2or3", False),  # only valid for custom transformers
    ],
)
def test_is_valid_python_compatibility(version, expected_is_valid):
    assert is_valid_python_compatibility(version) == expected_is_valid


def test_check_fmx(valid_package_dir):
    packager = FMEPackager(valid_package_dir)
    for transformer in packager.metadata.transformers:
        fmx_path = get_fmx_path(
            os.path.join(valid_package_dir, "transformers"), transformer.name
        )
        check_fmx(packager.metadata, transformer, fmx_path)


def test_check_fmx_with_compatibility_error(incompatible_package_dir):
    packager = FMEPackager(incompatible_package_dir)
    for transformer in packager.metadata.transformers:
        fmx_path = get_fmx_path(
            os.path.join(incompatible_package_dir, "transformers"), transformer.name
        )
        with pytest.raises(TransformerPythonCompatError):
            check_fmx(packager.metadata, transformer, fmx_path)


def test_check_custom_fmx(custom_package_dir):
    packager = FMEPackager(custom_package_dir)
    for transformer in packager.metadata.transformers:
        fmx_path = get_fmx_path(
            os.path.join(custom_package_dir, "transformers"), transformer.name
        )
        check_custom_fmx(packager.metadata, transformer, fmx_path)


def test_check_custom_fmx_with_error(incompatible_custom_package_dir):
    packager = FMEPackager(incompatible_custom_package_dir)
    for transformer in packager.metadata.transformers:
        fmx_path = get_fmx_path(
            os.path.join(incompatible_custom_package_dir, "transformers"),
            transformer.name,
        )
        with pytest.raises(CustomTransformerPythonCompatError):
            check_custom_fmx(packager.metadata, transformer, fmx_path)
