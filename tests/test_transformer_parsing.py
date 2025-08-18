from pathlib import Path

import pytest

from fme_packager.transformer import (
    load_transformer,
    CustomTransformerFmxFile,
    CustomTransformer,
    FmxFile,
    FmxjFile,
    parse_custom_transformer_header,
)


CWD = Path(__file__).parent.resolve()


def test_custom_transformer(custom_package_dir):
    fmx = load_transformer(Path(custom_package_dir) / "transformers" / "customFooBar.fmx")
    assert isinstance(fmx, CustomTransformerFmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 1
    for item in defs:
        assert isinstance(item, CustomTransformer)
        assert item.header.insert_mode == "Linked Always"
        assert item.name == "example.my-package.customFooBar"
        assert item.version == 1
        assert item.python_compatibility == "37"
        assert item.categories == ["Attributes"]
        assert item.aliases == []
        assert item.visible
        assert item.data_processing_types == []


def test_custom_transformer_encrypted_versioned(custom_package_dir):
    fmx = load_transformer(Path(custom_package_dir) / "transformers" / "customEncrypted2Ver.fmx")
    assert isinstance(fmx, CustomTransformerFmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 2
    for i, item in enumerate(defs):
        assert isinstance(item, CustomTransformer)
        assert item.header.insert_mode == "Embedded Always"
        assert item.name == "example.my-package.test"
        assert item.version == len(defs) - i
        assert item.python_compatibility == "310"
        assert item.is_encrypted == (i == 0)  # Latest version is encrypted
        assert item.visible
        assert item.data_processing_types == []


@pytest.mark.parametrize(
    "line",
    [
        '# TRANSFORMER_BEGIN example.my-package.customFooBar,1,Attributes,4d874d87-714f-41b4-9dfe-9748ebd8b565,"Linked Always",No,NO_PARALLELISM,,No,19238,YES,No,37',
        '# TRANSFORMER_BEGIN customCategoriesTest,1,"Attributes,""Format Specific""",92a7f1bd-938a-49db-92c4-48fb37426eb3,"Linked Always",No,NO_PARALLELISM,,No,25741,YES,No,,No,,source',
        '# TRANSFORMER_BEGIN example.data-processing-types.bothLinked,1,,,"Linked Always",No,NO_PARALLELISM,,No,25560,YES,No,,No,,both',
    ],
    ids=["simple", "multi-category", "no-category"],
)
def test_parse_custom_transformer_header(line):
    header = parse_custom_transformer_header(line)
    assert isinstance(header.version, int)
    assert isinstance(header.build_num, int)
    assert isinstance(header.deprecated, bool)
    assert header.insert_mode == "Linked Always"

    assert header.category != [""]
    if header.name == "customCategoriesTest":
        assert header.category == ["Attributes", "Format Specific"]

    assert header.data_processing_type != [""]
    if header.name == "example.data-processing-types.bothLinked":
        assert header.data_processing_type == ["both"]


def test_fmx_transformer(valid_package_dir):
    fmx = load_transformer(Path(valid_package_dir) / "transformers" / "MyGreeter.fmx")
    assert isinstance(fmx, FmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 1
    item = defs[0]
    assert item.name == "example.my-package.MyGreeter"
    assert item.version == 1
    assert item.python_compatibility == "36"
    assert item.categories == ["Integrations"]
    assert item.aliases == [
        "example.my-package.HerGreeter",
        "example.my-package.TheirGreeter",
        "example.my-package.OurGreeter",
    ]
    assert item.data_processing_types == []


def test_fmxj_transformer(fmxj_package_dir):
    fmx = load_transformer(Path(fmxj_package_dir) / "transformers" / "DemoGreeter.fmxj")
    assert isinstance(fmx, FmxjFile)
    defs = list(fmx.versions())
    assert len(defs) == 1
    item = defs[0]
    assert item.name == "example.my-package.DemoGreeter"
    assert item.version == 1
    assert not item.python_compatibility
    assert item.categories == ["Integrations"]
    assert item.aliases == ["example.my-package.NemoGreeter", "example.my-package.MemoGreeter"]
    assert item.data_processing_types == []


def test_fmx_transformer_data_processing_types(data_processing_types_package_dir):
    fmx = load_transformer(
        Path(data_processing_types_package_dir) / "transformers" / "AttributeFileReader.fmx"
    )
    assert isinstance(fmx, FmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 6  # Multiple versions in the file

    for item in defs:
        assert hasattr(item, "data_processing_types")
        assert item.data_processing_types == ["source"]

    # Test destination transformer
    fmx = load_transformer(
        Path(data_processing_types_package_dir) / "transformers" / "AttributeFileWriter.fmx"
    )
    assert isinstance(fmx, FmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 6  # Multiple versions in the file

    for item in defs:
        assert hasattr(item, "data_processing_types")
        assert item.data_processing_types == ["destination"]


def test_fmxj_transformer_data_processing_types(data_processing_types_package_dir):
    """Test that FMXJ transformers correctly parse conditional dataProcessingType logic."""
    fmx = load_transformer(
        Path(data_processing_types_package_dir) / "transformers" / "HTTPCaller.fmxj"
    )
    assert isinstance(fmx, FmxjFile)
    defs = list(fmx.versions())
    assert len(defs) == 8

    for item in defs:
        assert hasattr(item, "data_processing_types")
        # HTTPCaller has conditional logic with both "source" and "destination" values
        assert item.data_processing_types == ["destination", "source"]


def test_custom_transformer_data_processing_types(data_processing_types_package_dir):
    """Test that custom transformers handle missing data_processing_types gracefully."""
    fmx = load_transformer(
        Path(data_processing_types_package_dir) / "transformers" / "bothLinked.fmx"
    )
    assert isinstance(fmx, CustomTransformerFmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 1

    item = defs[0]
    assert hasattr(item, "data_processing_types")
    assert item.data_processing_types == ["both"]


def test_fmx_transformer_conditional_data_processing_types(data_processing_types_package_dir):
    """Test that FMX transformers correctly parse conditional dataProcessingType logic stored as JSON."""
    fmx = load_transformer(
        Path(data_processing_types_package_dir) / "transformers" / "BoxConnector.fmx"
    )
    assert isinstance(fmx, FmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 3

    for item in defs:
        assert hasattr(item, "data_processing_types")
        assert sorted(item.data_processing_types) == ["destination", "source"]
