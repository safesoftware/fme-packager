from __future__ import division, absolute_import, print_function, unicode_literals

import json
import pathlib
import shutil
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pathlib import Path

from fme_packager import summarizer
from fme_packager import cli
from fme_packager.metadata import FMEPackageMetadata
from fme_packager.operations import extract_fpkg
from fme_packager.summarizer import (
    TransformerFilenames,
    FormatFilenames,
    package_deprecated,
    Summarizer,
)

CWD = pathlib.Path(__file__).parent.resolve()


@pytest.mark.parametrize(
    "transformer_name, expected",
    [
        # Case 1: Transformer files do not exist
        (
            "non_existing_transformer",
            TransformerFilenames(filename=None, readme_filename=None),
        ),
        # Case 2: 'name' key is null
        (
            None,
            TransformerFilenames(filename=None, readme_filename=None),
        ),
        # Case 3: Transformer .fmx file exists but .fmxj file does not
        (
            "fmx_transformer",
            TransformerFilenames(
                filename=(Path("/base/dir") / "transformers" / "fmx_transformer.fmx").as_posix(),
                readme_filename=(
                    Path("/base/dir") / "transformers" / "fmx_transformer.md"
                ).as_posix(),
            ),
        ),
        # Case 4: Transformer .fmxj file exists but .fmx file does not
        (
            "fmxj_transformer",
            TransformerFilenames(
                filename=(Path("/base/dir") / "transformers" / "fmxj_transformer.fmxj").as_posix(),
                readme_filename=(
                    Path("/base/dir") / "transformers" / "fmxj_transformer.md"
                ).as_posix(),
            ),
        ),
    ],
)
def test__transformer_filenames(transformer_name, expected, mocker):
    # Mock Path.exists as an instance method (self is the path object)
    def mock_exists(self):
        path_str = str(self)
        if "non_existing_transformer" in path_str:
            return False
        if "fmx_transformer" in path_str and path_str.endswith(".fmx"):
            return True
        if "fmxj_transformer" in path_str and path_str.endswith(".fmxj"):
            return True
        if path_str.endswith(".md"):
            return True
        return False

    mocker.patch("pathlib.Path.exists", mock_exists)

    ctx = Summarizer("/base/dir")
    result = ctx.transformer_filenames(transformer_name)
    assert result == expected


@pytest.mark.parametrize(
    "format_name, exists, expected",
    [
        (
            "test_format",
            True,
            FormatFilenames(
                filename=(Path("/base/dir") / "formats" / "test_format.fmf").as_posix(),
                db_filename=(Path("/base/dir") / "formats" / "test_format.db").as_posix(),
                readme_filename=(Path("/base/dir") / "formats" / "test_format.md").as_posix(),
            ),
        ),
        (
            "non_existing_format",
            False,
            FormatFilenames(
                filename=None,
                db_filename=None,
                readme_filename=None,
            ),
        ),
    ],
)
def test__format_filenames(format_name, exists, expected):
    with patch("pathlib.Path.exists", return_value=exists):
        ctx = Summarizer("/base/dir")
        result = ctx.format_filenames(format_name)
        assert result == expected


def test__transformer_data(mock_transformer_file, mock_transformer):
    result = summarizer._transformer_data(mock_transformer_file)

    assert result["versions"] == [
        {
            "name": mock_transformer.name,
            "version": mock_transformer.version,
            "categories": mock_transformer.categories,
            "aliases": mock_transformer.aliases,
            "visible": mock_transformer.visible,
            "data_processing_types": mock_transformer.data_processing_types,
        }
    ]


def test__format_data():
    mock_format_line = (
        "SAFE.AIRTABLE.AIRTABLE|Airtable|NONE|BOTH|BOTH|NO||NON_SPATIAL|NO|YES|YES|YES|1|1|Airtable|NO"
        "|Airtable|3D,Coordinates"
    )

    result = summarizer._format_data(mock_format_line)
    assert result == {
        "visible": True,
        "fds_info": mock_format_line,
        "categories": ["3D", "Coordinates"],
    }


@pytest.fixture
def mock_transformers(mocker):
    # Mock the TransformerFile object
    mock_transformer_file1 = mocker.Mock()
    mock_transformer_file1.versions.return_value = [mocker.Mock(categories={"cat1", "cat2"})]

    mock_transformer_file2 = mocker.Mock()
    mock_transformer_file2.versions.return_value = [mocker.Mock(categories=None)]

    mock_transformer_file3 = mocker.Mock()
    mock_transformer_file3.versions.return_value = [mocker.Mock(categories={"cat3", "cat4"})]

    mock_transformer_file4 = mocker.Mock()
    mock_transformer_file4.versions.return_value = [mocker.Mock(categories={"cat4", "cat5"})]

    return [
        {
            "versions": [
                {"version": 1, "categories": {"cat6", "cat7"}},
                {"version": 2, "categories": {"cat1", "cat2"}},
            ]
        },
        {"versions": []},
        {"versions": [{"version": 1, "categories": {"cat3", "cat4"}}]},
        {"versions": [{"version": 1, "categories": {"cat4", "cat5"}}]},
    ]


@pytest.fixture
def mock_formats():
    return [
        {"categories": {"cat-f1", "cat3"}, "deprecated": False},
        {"categories": {"cat-f2", "cat4"}, "deprecated": False},
    ]


def test__get_all_categories(mock_transformers, mock_formats):
    result = summarizer._get_all_categories(mock_transformers, mock_formats)
    assert result == ["cat-f1", "cat-f2", "cat1", "cat2", "cat3", "cat4", "cat5"]


def test__add_content_description(mocker):
    transformer = {"readme_filename": "MyGreeter.md"}
    mocker.patch("builtins.open", mocker.mock_open(read_data="Test Description"))
    result = summarizer._content_description(transformer["readme_filename"])
    assert result["description"] == "Test Description"
    assert result["description_format"] == "md"


def test_package_transformers_deprecated(mock_transformers, mock_formats):
    # Case: All formats are not visible
    mock_formats[0]["visible"] = False
    mock_formats[1]["visible"] = False
    assert not package_deprecated(mock_transformers, mock_formats)

    # Case: One transformer version is not visible
    mock_transformers[0]["versions"][1]["visible"] = False
    assert not package_deprecated(mock_transformers, mock_formats)

    # Case: Multiple transformer versions are not visible
    mock_transformers[0]["versions"][1]["visible"] = False
    mock_transformers[2]["versions"][0]["visible"] = False
    assert not package_deprecated(mock_transformers, mock_formats)

    # Case: All transformer versions are not visible
    mock_transformers[3]["versions"][0]["visible"] = False
    assert package_deprecated(mock_transformers, mock_formats)

    mock_transformers[0]["versions"][0]["visible"] = True
    assert package_deprecated(mock_transformers, mock_formats)


def test_package_formats_deprecated(mock_transformers, mock_formats):
    # Case: All transformer versions are not visible
    mock_transformers[0]["versions"][1]["visible"] = False
    mock_transformers[2]["versions"][0]["visible"] = False
    mock_transformers[3]["versions"][0]["visible"] = False
    assert not package_deprecated(mock_transformers, mock_formats)

    # Case: One format is not visible
    mock_formats[0]["visible"] = False
    assert not package_deprecated(mock_transformers, mock_formats)

    # Case: All formats are not visible
    mock_formats[1]["visible"] = False
    assert package_deprecated(mock_transformers, mock_formats)


def test_package_all_visible(mock_transformers, mock_formats):
    for transformer in mock_transformers:
        for version in transformer["versions"]:
            version["visible"] = True
    for f in mock_formats:
        f["visible"] = True
    assert not package_deprecated(mock_transformers, mock_formats)


@pytest.mark.parametrize(
    "fpkg_path, expected_output_path",
    [
        (
            CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg",
            CWD / "fixtures" / "json_output" / "summarize_example.my-package-0.1.0.fpkg.json",
        ),
        (
            CWD / "fixtures" / "fpkgs" / "example.my-format-0.1.0.fpkg",
            CWD / "fixtures" / "json_output" / "summarize_example.my-format-0.1.0.fpkg.json",
        ),
        (
            CWD / "fixtures" / "fpkgs" / "example.my-package-deprecated-0.1.0.fpkg",
            CWD
            / "fixtures"
            / "json_output"
            / "summarize_example.my-package-deprecated-0.1.0.fpkg.json",
        ),
        (
            CWD / "fixtures" / "fpkgs" / "example.data-processing-types-0.1.0.fpkg",
            CWD
            / "fixtures"
            / "json_output"
            / "summarize_example.data-processing-types-0.1.0.fpkg.json",
        ),
    ],
    ids=["simple", "format", "deprecated", "data_processing_types"],
)
def test_summarize_fpkg(fpkg_path, expected_output_path):
    expected_output = json.loads(expected_output_path.read_text())
    result = summarizer.summarize_fpkg(fpkg_path)
    assert result == expected_output


def test_summarize_empty_fpkg(monkeypatch, tmp_path):
    mock_metadata = FMEPackageMetadata(
        {
            "fpkg_version": 1,
            "uid": "my-package",
            "publisher_uid": "example",
            "name": "My FME Package",
            "description": "A short description of my FME Package.",
            "version": "0.1.0",
            "minimum_fme_build": 19238,
            "author": {"name": "G Raymond", "email": "me@example.com"},
        }
    )
    monkeypatch.setattr(
        summarizer,
        "load_fpkg_metadata",
        lambda x: mock_metadata,
    )
    fpkg_path = CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg"
    expected_output = json.load(
        open(CWD / "fixtures" / "json_output" / "summarize_example.empty.json")
    )
    result = summarizer.summarize_fpkg(fpkg_path)
    assert result == expected_output


def test_summarize():
    runner = CliRunner()
    fpkg_path = str(CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg")
    result = runner.invoke(cli.summarize, [fpkg_path])
    assert result.exit_code == 0
    json.loads(result.output)


@pytest.fixture
def fpkg_dir_with_bad_data_processing_type(tmp_path):
    tmp_path = Path(tmp_path)
    fpkg_path = CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg"
    extract_fpkg(fpkg_path, tmp_path)

    # Modify the FMX file to have an invalid DATA_PROCESSING_TYPE
    fmx_path = tmp_path / "transformers" / "MyGreeter.fmx"
    fmx_txt = fmx_path.read_text()
    fmx_txt = fmx_txt.replace("ALIASES:", "ALIASES:\nDATA_PROCESSING_TYPE: bad value\n")
    fmx_path.write_text(fmx_txt)
    return tmp_path


def test_summarize_bad_data_processing_type(fpkg_dir_with_bad_data_processing_type):
    """
    Test that summarize_fpkg can run against an extracted FPKG,
    and rejects a bad data_processing_type in the FMX.
    """
    result = summarizer.summarize_fpkg(fpkg_dir_with_bad_data_processing_type)
    assert result["status"] == "error"
    assert result["message"].startswith(
        "The generated output did not conform to the schema: 'bad value' is not one of"
    )


@pytest.mark.parametrize(
    "subcommand", [cli.summarize, cli.verify, cli.pack], ids=lambda func: str(func)
)
def test_cli_bad_data_processing_type(fpkg_dir_with_bad_data_processing_type, subcommand):
    """
    Test that CLI commands fail with a bad data_processing_type in the FMX.
    """
    if subcommand is cli.verify:
        # Re-zip the extracted package back to .fpkg.
        # Can't use `fme-packager pack` because it's expected to reject this bad package.
        dest = str(fpkg_dir_with_bad_data_processing_type / "example.my-package-0.1.0.fpkg")
        shutil.make_archive(
            dest,
            "zip",
            root_dir=fpkg_dir_with_bad_data_processing_type,
        )
        Path(dest + ".zip").rename(dest)
        args = [dest]
    else:
        args = [fpkg_dir_with_bad_data_processing_type.as_posix()]

    result = CliRunner().invoke(subcommand, args)
    if subcommand is cli.pack:
        assert "The generated output did not conform to the schema" in str(result)
        assert result.exit_code != 0
    else:
        assert "The generated output did not conform to the schema" in result.output
        assert result.exit_code == 0
