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
from fme_packager.metadata import TransformerMetadata, FormatMetadata, FMEPackageMetadata
from fme_packager.operations import parse_formatinfo
from fme_packager.packager import (
    FMEPackager,
    is_valid_python_compatibility,
    get_formatinfo,
    get_format_visibility,
    enforce_metadata_unique_names,
)
from fme_packager.metadata import load_fpkg_metadata

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


def test_get_formatinfo(tmp_path):
    package_metadata = FMEPackageMetadata(
        {
            "uid": "package",
            "publisher_uid": "example",
            "package_content": {"formats": [{"name": "myformat"}]},
        }
    )
    format_metadata = FormatMetadata({"name": "myformat"})

    with pytest.raises(ValueError):
        filepath = tmp_path / "emptyformat.db"
        with open(filepath, "w") as f:
            f.write(";")
        get_formatinfo(package_metadata, format_metadata, filepath)

    with pytest.raises(ValueError):
        filepath = tmp_path / "formatnotfound.db"
        with open(filepath, "w") as f:
            f.write(
                "SAFE.CKAN.CKANDATASTORE|CKAN DataStore|NONE|BOTH|NONE|NO||NON_SPATIAL|NO|YES|YES|YES|3|3|CKAN|NO|CKAN"
            )
        get_formatinfo(package_metadata, format_metadata, filepath)

    filepath = tmp_path / "myformat.db"
    with open(filepath, "w") as f:
        f.writelines(
            "EXAMPLE.PACKAGE.MYFORMAT|My Format|NONE|BOTH|NONE|NO||NON_SPATIAL|NO|YES|YES|YES|3|3|MYFORMAT|NO|MYFORMAT|Coordinates\n"
            + "EXAMPLE.PACKAGE.NOTMYFORMAT|Not My Format|NONE|BOTH|NONE|NO||NON_SPATIAL|NO|YES|YES|YES|3|3|MYFORMAT|NO|MYFORMAT|Coordinates,3D"
        )

    formatinfo = get_formatinfo(package_metadata, format_metadata, filepath)
    assert formatinfo.FORMAT_NAME == "EXAMPLE.PACKAGE.MYFORMAT"


def test_get_format_visibility():
    base_formatinfo = parse_formatinfo(
        "EXAMPLE.PACKAGE.MYFORMAT|My Format|NONE|BOTH|NONE|NO||NON_SPATIAL|NO|YES|YES|YES|3|3|MYFORMAT|NO|MYFORMAT|Coordinates"
    )

    assert get_format_visibility(base_formatinfo._replace(DIRECTION="BOTH", VISIBLE="NO")) == ""
    assert get_format_visibility(base_formatinfo._replace(DIRECTION="BOTH", VISIBLE="YES")) == "rw"

    assert get_format_visibility(base_formatinfo._replace(DIRECTION="BOTH", VISIBLE="INPUT")) == "r"
    for visibility in ["YES", "INPUT"]:
        assert (
            get_format_visibility(base_formatinfo._replace(DIRECTION="INPUT", VISIBLE=visibility))
            == "r"
        )

    assert (
        get_format_visibility(base_formatinfo._replace(DIRECTION="BOTH", VISIBLE="OUTPUT")) == "w"
    )
    for visibility in ["YES", "OUTPUT"]:
        assert (
            get_format_visibility(base_formatinfo._replace(DIRECTION="OUTPUT", VISIBLE=visibility))
            == "w"
        )

    with pytest.raises(ValueError):
        assert get_format_visibility(base_formatinfo._replace(DIRECTION="INPUT", VISIBLE="OUTPUT"))


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


# [FMEENGINE-85295]
def test_duplicate_names_in_metadata(tmp_path):
    package_yml = tmp_path / "package.yml"
    package_yml.write_text(
        """uid: test_pkg
publisher_uid: test_pub
version: 1
minimum_fme_build: 25000
package_content:
  transformers:
    - name: MyTransformer
      version: 1
    - name: MyTransformer
      version: 1
  formats:
    - name: MyFormat
    - name: MyFormat
  web_services:
    - name: MyWebService.xml
    - name: MyWebService.xml
  web_filesystems: []
  python_packages: []
"""
    )
    metadata = load_fpkg_metadata(str(tmp_path))
    with pytest.raises(ValueError):
        enforce_metadata_unique_names(metadata)
