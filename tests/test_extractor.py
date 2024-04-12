import json
import pathlib

import pytest

from fme_packager import extractor

CWD = pathlib.Path(__file__).parent.resolve()


def test__parse_transformer():
    transformer_path = CWD / "fixtures" / "valid_package" / "transformers" / "MyGreeter.fmx"
    transformer_content = open(transformer_path).read()

    result = extractor._parse_transformer(transformer_content)

    assert len(result) == 16

    assert result == {
        "aliases": None,
        "attributes_added": "Output:_greeting <REJECTED>:fme_rejection_code",
        "category": "Integrations",
        "changes": "",
        "feature_holding": "NONE",
        "input_tags": "<BLANK>",
        "output_tags": "Output <REJECTED>",
        "parameter_default": "World",
        "parameter_name": "FIRST_NAME",
        "parameter_prompt": "First Name",
        "parameter_type": "STRING_OR_ATTR_ENCODED",
        "preserves_attributes": "YES",
        "python_compatibility": "36",
        "transformer_name": "example.my-package.MyGreeter",
        "version": "1",
        "visible": "yes",
    }


def test__add_transformer_description(mocker):
    transformer = {"readme_filename": "MyGreeter.md"}
    mocker.patch("builtins.open", mocker.mock_open(read_data="Test Description"))
    result = extractor._add_transformer_description(transformer)
    assert result["description"] == "Test Description"
    assert result["description_format"] == "md"


@pytest.mark.parametrize("visible,expected", [
    ("no", True),
    ("NO", True),
    ("yes", False),
    ("YES", False),
    ("garbage value", True),
])
def test__visible_to_deprecated(visible, expected):
    transformer = {"visible": visible}
    result = extractor._visible_to_deprecated(transformer)
    assert result["deprecated"] is expected


@pytest.mark.parametrize("aliases,expected", [
    ("", []),
    ("alias1", ["alias1"]),
    ("alias1 alias2 alias3", ["alias1", "alias2", "alias3"]),
    ("alias,with,commas", ["alias,with,commas"]),
])
def test__split_aliases(aliases, expected):
    transformer = {"aliases": aliases}
    result = extractor._split_aliases(transformer)
    assert result["aliases"] == expected


@pytest.mark.parametrize("category,expected", [
    ("category1", ["category1"]),
    ("", []),
    ("category1,category2", ["category1", "category2"]),
    ("category with spaces", ["category with spaces"]),
])
def test__split_categories(category, expected):
    transformer = {"category": category}
    result = extractor._split_categories(transformer)
    assert result["categories"] == expected


def test__get_all_categories():
    transformers = [
        {"categories": ["category1", "category2"]},
        {"categories": ["category2", "category3"]},
    ]
    result = extractor._get_all_categories(transformers)
    assert result == {"category1", "category2", "category3"}


def test_summarize_fpkg():
    # Path to the fpkg file
    fpkg_path = CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg"

    # Expected JSON output
    expected_output = json.load(open(CWD / "fixtures" / "json_output" / "summarize_example.my-package-0.1.0.fpkg.json"))

    # Run the summarize_fpkg function
    result = json.loads(extractor.summarize_fpkg(str(fpkg_path)))

    # Compare the result to the expected output
    assert result == expected_output
