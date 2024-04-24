import json
import pathlib
import tempfile

import pytest
import yaml
from click.testing import CliRunner

from fme_packager import summarizer
from fme_packager.cli import summarize
from fme_packager.summarizer import TransformerFilenames
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


def test__get_all_categories(mock_transformers):
    result = summarizer._get_all_categories(mock_transformers)
    assert result == {"cat1", "cat2", "cat3", "cat4", "cat5"}


def test__add_transformer_description(mocker):
    transformer = {"readme_filename": "MyGreeter.md"}
    mocker.patch("builtins.open", mocker.mock_open(read_data="Test Description"))
    result = summarizer._transformer_description(transformer)
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


def test_summarize_fpkg():
    fpkg_path = CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg"
    expected_output = json.load(
        open(CWD / "fixtures" / "json_output" / "summarize_example.my-package-0.1.0.fpkg.json")
    )
    result = json.loads(summarizer.summarize_fpkg(str(fpkg_path)))
    assert result == expected_output


def test_summarize():
    runner = CliRunner()
    fpkg_path = str(CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg")
    result = runner.invoke(summarize, [fpkg_path])
    assert result.exit_code == 0
    json.loads(result.output)
