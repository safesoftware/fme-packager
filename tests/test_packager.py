import os
import pathlib
from zipfile import ZipFile

import pytest
from click.testing import CliRunner

from fme_packager.cli import pack
from fme_packager.exception import (
    TransformerPythonCompatError,
    CustomTransformerPythonCompatError,
)
from fme_packager.metadata import TransformerMetadata
from fme_packager.packager import (
    FMEPackager,
    is_valid_python_compatibility,
)


CWD = pathlib.Path(__file__).parent.resolve()


@pytest.mark.parametrize(
    "version, expected_is_valid",
    [
        ("26", False),
        ("27", False),
        ("ArcGISDesktop", False),
        ("34", False),
        ("35", True),
        ("36", True),
        ("37", True),
        ("3.8.9", False),  # 3.x.x is invalid version syntax for PYTHON_COMPATIBILITY
        ("2or3", False),  # only valid for custom transformers
    ],
)
def test_is_valid_python_compatibility(version, expected_is_valid):
    assert is_valid_python_compatibility(version) == expected_is_valid


@pytest.mark.parametrize(
    "transformer_path,metadata,expected_exc",
    [
        ("valid_package/transformers/MyGreeter.fmx", None, None),
        (
            "valid_package/transformers/MyGreeter.fmx",
            {"name": "TheirGreeter", "version": 1},
            "Name must be",
        ),
        ("incompatible_package/transformers/MyGreeter.fmx", None, TransformerPythonCompatError),
        (
            "incompatible_custom_package/transformers/epochToTimestamp29.fmx",
            None,
            CustomTransformerPythonCompatError,
        ),
        ("custom_package/transformers/customFooBar.fmx", None, None),
        ("custom_package/transformers/epochToTimestamp29.fmx", None, None),
        (
            "custom_package/transformers/customEncrypted2Ver.fmx",
            {"name": "test", "version": 2},
            'Custom transformer Insert Mode must be "Linked Always"',
        ),
        ("fmxj_package/transformers/DemoGreeter.fmxj", None, None),
    ],
)
def test_validate_transformer(transformer_path, metadata, expected_exc):
    """
    Load and validate a transformer.
    If expected_exc is given and is an exception, it's expected to be raised.
    If it's a string, it's expected to be a substring in the raised exception message.
    The package.yml in the transformer's parent folder is automatically loaded.
    The metadata argument overrides the transformer's entry in package.yml.
    If the transformer has no entry in package.yml, the metadata must be provided.
    """
    transformer_abs_path = CWD / "fixtures" / transformer_path
    packager = FMEPackager(transformer_abs_path.parent.parent)
    if metadata:
        metadata = TransformerMetadata(metadata)
    else:
        try:
            metadata = {i.name: i for i in packager.metadata.transformers}[
                transformer_abs_path.stem
            ]
        except KeyError as e:
            raise KeyError(
                f"{transformer_abs_path.stem} not in package.yml, but no metadata given"
            ) from e

    if not expected_exc:
        # Expect success
        packager.validate_transformer(transformer_abs_path, metadata)
    elif isinstance(expected_exc, str):
        # Expect a keywords in exception message
        with pytest.raises(Exception) as exc:
            packager.validate_transformer(transformer_abs_path, metadata)
        assert expected_exc in str(exc.value)
    else:
        # Expect a particular exception class
        with pytest.raises(expected_exc):
            packager.validate_transformer(transformer_abs_path, metadata)


@pytest.mark.parametrize("package_name", ["valid_package", "fmxj_package"])
def test_pack(package_name):
    runner = CliRunner()
    result = runner.invoke(pack, [str(CWD / "fixtures" / package_name)])
    assert result.exit_code == 0

    # Sanity check: expect FPKG to exist and contain package.yml at root level
    dist_dir = CWD / "fixtures" / package_name / "dist"
    fpkg_name = os.listdir(dist_dir)[0]
    with ZipFile(dist_dir / fpkg_name) as z:
        assert "package.yml" in z.namelist()
