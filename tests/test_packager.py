import os
import pathlib
from zipfile import ZipFile
from copy import deepcopy

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
    enforce_valid_pyz,
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


@pytest.mark.parametrize(
    "package_name", ["valid_package", "fmxj_package", "application_plugins_package"]
)
def test_pack(package_name):
    runner = CliRunner()
    result = runner.invoke(pack, [str(CWD / "fixtures" / package_name)])
    assert result.exit_code == 0

    # Sanity check: expect FPKG to exist and contain package.yml at root level
    dist_dir = CWD / "fixtures" / package_name / "dist"
    fpkg_name = os.listdir(dist_dir)[0]
    with ZipFile(dist_dir / fpkg_name) as z:
        assert "package.yml" in z.namelist()


def test_enforce_valid_pyz_valid(tmp_path):
    pyz = tmp_path / "worker.pyz"
    with ZipFile(pyz, "w") as z:
        z.writestr("__main__.py", "print('hi')")
    enforce_valid_pyz(pyz)  # Does not raise


def test_enforce_valid_pyz_missing(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        enforce_valid_pyz(tmp_path / "missing.pyz")


def test_enforce_valid_pyz_not_a_zip(tmp_path):
    pyz = tmp_path / "worker.pyz"
    pyz.write_text("not a zip")
    with pytest.raises(ValueError, match="not a valid pyz"):
        enforce_valid_pyz(pyz)


def test_enforce_valid_pyz_missing_main(tmp_path):
    pyz = tmp_path / "worker.pyz"
    with ZipFile(pyz, "w") as z:
        z.writestr("other.py", "x = 1")
    with pytest.raises(ValueError, match="missing __main__.py"):
        enforce_valid_pyz(pyz)


def _make_plugin_package(tmp_path, plugin_file):
    """Create a minimal valid plugin package whose single entry references plugin_file."""
    pkg_dir = tmp_path / "pkg"
    (pkg_dir / "application_plugins").mkdir(parents=True)
    yml = deepcopy(PACKAGE_YML_TEMPLATE)
    yml["publisher_uid"] = "safe"
    yml["package_content"] = {
        "application_plugins": [
            {
                "name": "agent-plugin",
                "entries": [{"platforms": ["windows-x64"], "file": plugin_file, "type": "pyz"}],
            }
        ]
    }
    with (pkg_dir / "package.yml").open("w") as f:
        YAML().dump(yml, f)
    return pkg_dir


@pytest.mark.parametrize("plugin_file", ["../secret", "../../secret"])
def test_copy_application_plugins_rejects_traversal(tmp_path, plugin_file):
    # A file outside the application_plugins folder that must not be copied.
    (tmp_path / "secret").write_text("secret")
    pkg_dir = _make_plugin_package(tmp_path, plugin_file)
    packager = FMEPackager(pkg_dir)
    packager.build_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="must be inside the"):
        packager._copy_application_plugins()


def test_copy_application_plugins_rejects_absolute_path(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("secret")
    pkg_dir = _make_plugin_package(tmp_path, str(secret))
    packager = FMEPackager(pkg_dir)
    packager.build_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="must be inside the"):
        packager._copy_application_plugins()


def _write_valid_pyz(path):
    with ZipFile(path, "w") as z:
        z.writestr("__main__.py", "print('hi')")


def test_copy_application_plugins_copies_pyz(tmp_path):
    pkg_dir = _make_plugin_package(tmp_path, "worker.pyz")
    _write_valid_pyz(pkg_dir / "application_plugins" / "worker.pyz")
    packager = FMEPackager(pkg_dir)
    packager.build_dir.mkdir(parents=True, exist_ok=True)
    packager._copy_application_plugins()
    assert (packager.build_dir / "application_plugins" / "worker.pyz").is_file()


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
    # https://github.com/python-jsonschema/jsonschema/commit/a1d4cb3b94a83f209ebde1506a18b297a42b6219
    pytest.param(
        lambda x: x["package_content"].update({"transformers": []}),
        "[] is too short",
        id="empty_content_subkey_lt_py_311",
        marks=pytest.mark.skipif(
            os.sys.version_info >= (3, 11),
            reason="jsonschema pinned on PY<3.11, which has different msg",
        ),
    ),
    pytest.param(
        lambda x: x["package_content"].update({"transformers": []}),
        "[] should be non-empty",
        id="empty_content_subkey",
        marks=pytest.mark.skipif(
            os.sys.version_info < (3, 11),
            reason="jsonschema pinned on PY<3.11, which has different msg",
        ),
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
    pytest.param(
        lambda x: x.update({"unsupported_from_build": 25000}),
        "25000 is less than the minimum",
        id="unsupported_from_build_too_low",
    ),
    pytest.param(
        lambda x: x.update({"minimum_fme_build": 26000, "unsupported_from_build": 26000}),
        "unsupported_from_build must be greater than minimum_fme_build",
        id="unsupported_from_build_lte_minimum_fme_build",
    ),
    pytest.param(
        lambda x: x.update({"minimum_fme_build": 26000, "unsupported_from_build": 26001}),
        None,
        id="unsupported_from_build_valid",
    ),
    pytest.param(
        lambda x: (
            x.update({"publisher_uid": "safe"}),
            x["package_content"].update(
                {
                    "application_plugins": [
                        {
                            "name": "agent-plugin",
                            "entries": [
                                {
                                    "platforms": ["windows-x64-cp314"],
                                    "file": "agent-plugin.win.0.1.pyz",
                                    "type": "pyz",
                                    "env": {"PEX_ROOT": "%writabledir%/.pycache"},
                                    "command": [
                                        "%pythoninterpreter%",
                                        "%plugindir%/agent-plugin.win.0.1.pyz",
                                        "serve",
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ),
        ),
        None,
        id="application_plugin_valid",
    ),
    pytest.param(
        lambda x: (
            x.update({"publisher_uid": "safe"}),
            x["package_content"].update(
                {
                    "application_plugins": [
                        {
                            "name": "agent-plugin",
                            "entries": [
                                {
                                    "platforms": ["windows-x64-cp314"],
                                    "file": "agent-plugin.win.0.1.pyz",
                                    "type": "pyz",
                                }
                            ],
                        }
                    ]
                }
            ),
        ),
        None,
        id="application_plugin_env_command_optional",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "agent-plugin",
                        "entries": [
                            {
                                "platforms": ["windows-x64"],
                                "file": "agent-plugin.win.0.1.pyz",
                                "type": "pyz",
                            }
                        ],
                    }
                ]
            }
        ),
        "application_plugins are only allowed for the 'safe' publisher",
        id="application_plugin_non_safe_publisher",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "agent-plugin",
                        "entries": [{"platforms": ["windows-x64"], "file": "x.pyz", "type": "pyz"}],
                    },
                    {
                        "name": "agent-plugin",
                        "entries": [{"platforms": ["macosx-x64"], "file": "y.pyz", "type": "pyz"}],
                    },
                ]
            }
        ),
        "agent-plugin is defined in application_plugins more than once",
        id="application_plugin_dupe_name",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "Agent_Plugin",
                        "entries": [{"platforms": ["windows-x64"], "file": "x.pyz", "type": "pyz"}],
                    }
                ]
            }
        ),
        "Failed validating 'pattern'",
        id="application_plugin_bad_name",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "agent-plugin",
                        "entries": [
                            {"platforms": ["windows-sparc"], "file": "x.pyz", "type": "pyz"}
                        ],
                    }
                ]
            }
        ),
        "Failed validating 'pattern'",
        id="application_plugin_bad_platform",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "agent-plugin",
                        "entries": [{"platforms": ["windows-x64"], "type": "pyz"}],
                    }
                ]
            }
        ),
        "'file' is a required property",
        id="application_plugin_missing_file",
    ),
    pytest.param(
        lambda x: (
            x.update({"publisher_uid": "safe"}),
            x["package_content"].update(
                {
                    "application_plugins": [
                        {
                            "name": "agent-plugin",
                            "entries": [
                                {
                                    "platforms": ["windows-x64"],
                                    "file": "agent-plugin.bin",
                                    "type": "pyz",
                                }
                            ],
                        }
                    ]
                }
            ),
        ),
        None,
        id="application_plugin_non_pyz_filename_allowed",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "agent-plugin",
                        "entries": [{"platforms": ["windows-x64"], "file": "x.pyz"}],
                    }
                ]
            }
        ),
        "'type' is a required property",
        id="application_plugin_entry_missing_type",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {
                "application_plugins": [
                    {
                        "name": "agent-plugin",
                        "entries": [{"platforms": ["windows-x64"], "file": "x.exe", "type": "exe"}],
                    }
                ]
            }
        ),
        "Failed validating 'enum'",
        id="application_plugin_entry_bad_type",
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {"application_plugins": [{"name": "agent-plugin", "entries": []}]}
        ),
        "[] is too short",
        id="application_plugin_empty_entries_lt_py_311",
        marks=pytest.mark.skipif(
            os.sys.version_info >= (3, 11),
            reason="jsonschema pinned on PY<3.11, which has different msg",
        ),
    ),
    pytest.param(
        lambda x: x["package_content"].update(
            {"application_plugins": [{"name": "agent-plugin", "entries": []}]}
        ),
        "[] should be non-empty",
        id="application_plugin_empty_entries",
        marks=pytest.mark.skipif(
            os.sys.version_info < (3, 11),
            reason="jsonschema pinned on PY<3.11, which has different msg",
        ),
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
