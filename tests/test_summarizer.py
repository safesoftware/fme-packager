import json
import pathlib
import tempfile
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner
from pathlib import Path

from fme_packager import summarizer
from fme_packager.cli import summarize
from fme_packager.summarizer import TransformerFilenames, FormatFilenames, _package_deprecated
from tests.conftest import mock_transformer, mock_transformer_file

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
                filename="transformers/fmx_transformer.fmx",
                readme_filename="transformers/fmx_transformer.md",
            ),
        ),
        # Case 4: Transformer .fmxj file exists but .fmx file does not
        (
            "fmxj_transformer",
            TransformerFilenames(
                filename="transformers/fmxj_transformer.fmxj",
                readme_filename="transformers/fmxj_transformer.md",
            ),
        ),
    ],
)
def test__transformer_filenames(transformer_name, expected, mocker):
    def side_effect(path):
        if "non_existing_transformer" in path:
            return False
        if "fmx_transformer" in path and path.endswith(".fmx"):
            return True
        if "fmxj_transformer" in path and path.endswith(".fmxj"):
            return True
        if path.endswith(".md"):
            return True
        return False

    mocker.patch("os.path.exists", side_effect=side_effect)

    result = summarizer._transformer_filenames(transformer_name)
    assert result == expected


@pytest.mark.parametrize(
    "format_name, exists, expected",
    [
        (
            "test_format",
            True,
            FormatFilenames(
                filename=str(Path("formats") / "test_format.fmf"),
                db_filename=str(Path("formats") / "test_format.db"),
                readme_filename=str(Path("formats") / "test_format.md"),
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
    with patch("os.path.exists", return_value=exists):
        result = summarizer._format_filenames(format_name)
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


def test__parsed_manifest():
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yml") as temp:
        # Write some data to the file
        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }
        yaml.dump(data, temp)

    # Call the function with the path of the temporary file
    result = summarizer._parsed_manifest(pathlib.Path(temp.name))

    # Assert that the returned dictionary matches the data we wrote to the file
    assert result == data


def test_package_transformers_deprecated(mock_transformers, mock_formats):
    # Case: All formats are not visible
    mock_formats[0]["visible"] = False
    mock_formats[1]["visible"] = False
    assert not _package_deprecated(mock_transformers, mock_formats)

    # Case: One transformer version is not visible
    mock_transformers[0]["versions"][1]["visible"] = False
    assert not _package_deprecated(mock_transformers, mock_formats)

    # Case: Multiple transformer versions are not visible
    mock_transformers[0]["versions"][1]["visible"] = False
    mock_transformers[2]["versions"][0]["visible"] = False
    assert not _package_deprecated(mock_transformers, mock_formats)

    # Case: All transformer versions are not visible
    mock_transformers[3]["versions"][0]["visible"] = False
    assert _package_deprecated(mock_transformers, mock_formats)

    mock_transformers[0]["versions"][0]["visible"] = True
    assert _package_deprecated(mock_transformers, mock_formats)


def test_package_formats_deprecated(mock_transformers, mock_formats):
    # Case: All transformer versions are not visible
    mock_transformers[0]["versions"][1]["visible"] = False
    mock_transformers[2]["versions"][0]["visible"] = False
    mock_transformers[3]["versions"][0]["visible"] = False
    assert not _package_deprecated(mock_transformers, mock_formats)

    # Case: One format is not visible
    mock_formats[0]["visible"] = False
    assert not _package_deprecated(mock_transformers, mock_formats)

    # Case: All formats are not visible
    mock_formats[1]["visible"] = False
    assert _package_deprecated(mock_transformers, mock_formats)


def test_package_all_visible(mock_transformers, mock_formats):
    for transformer in mock_transformers:
        for version in transformer["versions"]:
            version["visible"] = True
    for f in mock_formats:
        f["visible"] = True
    assert not _package_deprecated(mock_transformers, mock_formats)


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
    ],
)
def test_summarize_fpkg(fpkg_path, expected_output_path):
    expected_output = json.load(open(expected_output_path))
    result = json.loads(summarizer.summarize_fpkg(str(fpkg_path)))
    assert result == expected_output


def test_summarize_empty_fpkg(monkeypatch):
    monkeypatch.setattr(
        summarizer,
        "_parsed_manifest",
        lambda x: {
            "fpkg_version": 1,
            "uid": "my-package",
            "publisher_uid": "example",
            "name": "My FME Package",
            "description": "A short description of my FME Package.",
            "version": "0.1.0",
            "minimum_fme_build": 19238,
            "author": {"name": "G Raymond", "email": "me@example.com"},
        },
    )
    fpkg_path = CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg"
    expected_output = json.load(
        open(CWD / "fixtures" / "json_output" / "summarize_example.empty.json")
    )
    result = json.loads(summarizer.summarize_fpkg(str(fpkg_path)))
    assert result == expected_output


def test_summarize():
    runner = CliRunner()
    fpkg_path = str(CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg")
    result = runner.invoke(summarize, [fpkg_path])
    assert result.exit_code == 0
    json.loads(result.output)
