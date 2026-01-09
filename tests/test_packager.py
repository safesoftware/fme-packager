import os
import pathlib
from zipfile import ZipFile
from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner
from jsonschema import ValidationError
from ruamel.yaml import YAML

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
    validate_metadata,
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
            raise KeyError(f"{transformer_abs_path.stem} not in package.yml") from e

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


PACKAGE_YML_TEMPLATE = {
    "uid": "test-uid",
    "publisher_uid": "test-publisher",
    "name": "test-name",
    "description": "test_description",
    "author": {
        "name": "name",
        "email": "a@a.com",
    },
    "version": "1.0.0",
    "minimum_fme_build": 25000,
    "fpkg_version": 1,
    "package_content": {
        "transformers": [
            {"name": "MyTransformer", "version": 1},
        ],
        "formats": [
            {"name": "MyFormat"},
        ],
        "web_services": [
            {"name": "MyWebService.xml"},
        ],
    },
}


def _dupe_content(yml):
    # Add a copy of the first element to each package_content sublist
    for key, value in yml["package_content"].items():
        if not value:
            continue
        value.append(value[0])


PACKAGE_YML_VALIDATION_CASES = [
    pytest.param(None, None, id="valid"),
    pytest.param(_dupe_content, "has non-unique elements", id="dupe_content"),
    pytest.param(
        lambda x: x.update(
            {
                "package_content": {
                    "transformers": [
                        {"name": "XFormer", "version": 1},
                        {"name": "XFormer", "version": 0},
                    ]
                }
            }
        ),
        "xformer is defined in transformers more than once",
        id="dupe_content_name_only",  # FMEENGINE-85295
    ),
    pytest.param(
        lambda x: x["package_content"].update({}),
        None,
        id="empty_content_valid",
    ),
    pytest.param(
        lambda x: x["package_content"].update({"transformers": []}),
        "is too short",
        id="empty_content_subkey",
    ),
    pytest.param(
        lambda x: x.update({"version": 1}),
        "Failed validating 'type'",
        id="version_not_str",
    ),
    pytest.param(
        lambda x: x.update({"version": "a.b.c"}),
        "Failed validating 'pattern'",
        id="version_not_semantic",
    ),
    pytest.param(
        lambda x: x.update({"foo": "bar"}),
        "Additional properties are not allowed",
        id="extra_root_key",
    ),
]
for required_key in (
    "uid",
    "publisher_uid",
    "name",
    "description",
    "author",
    "version",
    "minimum_fme_build",
    "fpkg_version",
    "package_content",
):
    PACKAGE_YML_VALIDATION_CASES.append(
        pytest.param(
            lambda x, key=required_key: x.pop(key),
            f"'{required_key}' is a required property",
            id=f"missing_{required_key}",
        )
    )
for key in ("uid", "publisher_uid"):
    PACKAGE_YML_VALIDATION_CASES.append(
        pytest.param(
            lambda x, key=key: x.__setitem__(key, "a_b"),
            "Failed validating 'pattern'",
            id=f"bad_{key}",
        )
    )


@pytest.mark.parametrize("mutation_func, expect_msg", PACKAGE_YML_VALIDATION_CASES)
def test_package_yml_validation(mutation_func, expect_msg, tmp_path):
    """
    Starting with a valid package.yml template, apply mutations and validate.
    If expect_msg is given, it's expected to be a substring in the raised exception message.
    If not given, validation is expected to succeed.
    """
    package_yml_dict = deepcopy(PACKAGE_YML_TEMPLATE)
    if mutation_func:
        mutation_func(package_yml_dict)

    with (tmp_path / "package.yml").open("w") as f:
        YAML().dump(package_yml_dict, f)
    metadata = load_fpkg_metadata(tmp_path)

    if expect_msg:
        with pytest.raises((ValidationError, ValueError)) as exc:
            validate_metadata(metadata)
        assert expect_msg in str(exc.value)
    else:
        # Expect success
        validate_metadata(metadata)
