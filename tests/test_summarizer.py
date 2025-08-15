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
from fme_packager.summarizer import (
    TransformerFilenames,
    FormatFilenames,
    _package_deprecated,
    SummarizerContext,
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

    ctx = SummarizerContext("/base/dir")
    result = ctx._transformer_filenames(transformer_name)
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
        ctx = SummarizerContext("/base/dir")
        result = ctx._format_filenames(format_name)
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
        (
            CWD / "fixtures" / "fpkgs" / "example.data-processing-types-0.1.0.fpkg",
            CWD
            / "fixtures"
            / "json_output"
            / "summarize_example.data-processing-types-0.1.0.fpkg.json",
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


def test__enhance_transformer_info(mocker):
    # Create mock data for the test
    transformers = [
        {"name": "transformer1", "version": "1.0"},
        {"name": "transformer2", "version": "2.0"},
    ]
    base_dir = "/test/dir"

    ctx = SummarizerContext(base_dir)

    # Mock the necessary functions
    transformer_filenames_mock = mocker.patch.object(
        ctx,
        "_transformer_filenames",
        return_value=TransformerFilenames(filename="test_filename", readme_filename="test_readme"),
    )
    mocker.patch("fme_packager.summarizer.load_transformer")
    mocker.patch.object(
        summarizer,
        "_transformer_data",
        return_value={"versions": [{"name": "test", "version": "1.0"}]},
    )
    mocker.patch.object(
        summarizer,
        "_content_description",
        return_value={"description": "test description", "description_format": "md"},
    )

    # Call the method
    result = ctx._enhance_transformer_info(transformers)

    # Verify the calls to other functions with the correct parameters
    assert transformer_filenames_mock.call_count == 2
    transformer_filenames_mock.assert_any_call("transformer1")
    transformer_filenames_mock.assert_any_call("transformer2")

    # Verify the function returns the expected result
    assert len(result) == 2
    assert "latest_version" in result[0]
    assert "latest_version" in result[1]
    assert result[0]["latest_version"] == "1.0"
    assert result[1]["latest_version"] == "2.0"


def test__enhance_web_service_info(mocker):
    # Create mock data for the test
    web_services = [
        {"name": "service1.xml"},
        {"name": "service2"},
    ]
    base_dir = "/test/dir"

    ctx = SummarizerContext(base_dir)

    # Mock the necessary functions
    web_service_path_mock = mocker.patch(
        "fme_packager.summarizer._web_service_path", return_value="web_services/test_path"
    )
    parse_web_service_mock = mocker.patch(
        "fme_packager.summarizer._parse_web_service",
        return_value={
            "help_url": "http://example.com",
            "description": "Test description",
            "markdown_description": "# Test",
            "connection_description": "Connection info",
            "markdown_connection_description": "# Connection",
        },
    )

    # Call the method
    result = ctx._enhance_web_service_info(web_services)

    # Verify the web_service_path was called correctly
    web_service_path_mock.assert_any_call("service1.xml")
    web_service_path_mock.assert_any_call("service2")

    # Verify parse_web_service was called with correct paths including base_dir
    expected_path1 = Path(base_dir) / "web_services/test_path"
    parse_web_service_mock.assert_any_call(expected_path1)

    # Verify XML extension was removed
    assert result[0]["name"] == "service1"
    assert result[1]["name"] == "service2"

    # Verify all expected fields were populated
    for service in result:
        assert service["help_url"] == "http://example.com"
        assert service["description"] == "Test description"
        assert service["markdown_description"] == "# Test"
        assert service["connection_description"] == "Connection info"
        assert service["markdown_connection_description"] == "# Connection"


def test__enhance_format_info(mocker):
    # Create mock data for the test
    formats = [
        {"name": "format1"},
        {"name": "format2"},
    ]
    publisher_uid = "test_publisher"
    uid = "test_uid"
    base_dir = "/test/dir"

    ctx = SummarizerContext(base_dir)

    # Mock the necessary functions
    format_filenames_mock = mocker.patch.object(
        ctx,
        "_format_filenames",
        return_value=FormatFilenames(
            filename="test_format.fmf",
            readme_filename="test_readme.md",
            db_filename="test_format.db",
        ),
    )
    mocker.patch("fme_packager.summarizer._load_format_line", return_value="format_line_content")
    mocker.patch.object(
        summarizer,
        "_format_data",
        return_value={
            "visible": True,
            "fds_info": "format_info",
            "categories": ["category1", "category2"],
        },
    )
    mocker.patch.object(
        summarizer,
        "_content_description",
        return_value={"description": "format description", "description_format": "md"},
    )

    # Call the method
    result = ctx._enhance_format_info(publisher_uid, uid, formats)

    # Verify the format_filenames was called correctly with base_dir
    format_filenames_mock.assert_any_call("format1")
    format_filenames_mock.assert_any_call("format2")

    # Verify the short_name and name transformations
    assert result[0]["short_name"] == "format1"
    assert result[0]["name"] == "test_publisher.test_uid.format1"
    assert result[1]["short_name"] == "format2"
    assert result[1]["name"] == "test_publisher.test_uid.format2"

    # Verify data was added from _format_data and _content_description
    for format_item in result:
        assert format_item["visible"] is True
        assert format_item["fds_info"] == "format_info"
        assert format_item["categories"] == ["category1", "category2"]
        assert format_item["description"] == "format description"
        assert format_item["description_format"] == "md"
