import os
import pathlib

from fme_packager.transformer import (
    load_transformer,
    CustomTransformerFmxFile,
    CustomTransformer,
    FmxFile,
    FmxjFile,
)


CWD = pathlib.Path(__file__).parent.resolve()


def test_custom_transformer(custom_package_dir):
    fmx = load_transformer(os.path.join(custom_package_dir, "transformers", "customFooBar.fmx"))
    assert isinstance(fmx, CustomTransformerFmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 1
    for item in defs:
        assert isinstance(item, CustomTransformer)
        assert item.header.insert_mode == '"Linked Always"'
        assert item.name == "example.my-package.customFooBar"
        assert item.version == 1
        assert item.python_compatibility == "37"
        assert item.categories == ["Attributes"]
        assert item.aliases == []


def test_custom_transformer_encrypted_versioned(custom_package_dir):
    fmx = load_transformer(
        os.path.join(custom_package_dir, "transformers", "customEncrypted2Ver.fmx")
    )
    assert isinstance(fmx, CustomTransformerFmxFile)
    defs = list(fmx.versions())
    assert len(defs) == 2
    for i, item in enumerate(defs):
        assert isinstance(item, CustomTransformer)
        assert item.header.insert_mode == '"Embedded Always"'
        assert item.name == "example.my-package.test"
        assert item.version == len(defs) - i
        assert item.python_compatibility == "310"
        assert item.is_encrypted == (i == 0)  # Latest version is encrypted


def test_fmx_transformer(valid_package_dir):
    fmx = load_transformer(os.path.join(valid_package_dir, "transformers", "MyGreeter.fmx"))
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


def test_fmxj_transformer(valid_package_dir):
    fmx = load_transformer(CWD / "fixtures" / "fmxj_package" / "transformers" / "DemoGreeter.fmxj")
    assert isinstance(fmx, FmxjFile)
    defs = list(fmx.versions())
    assert len(defs) == 1
    item = defs[0]
    assert item.name == "example.my-package.DemoGreeter"
    assert item.version == 1
    assert not item.python_compatibility
    assert item.categories == ["Integrations"]
    assert item.aliases == [
        "example.my-package.NemoGreeter",
        "example.my-package.MemoGreeter"
    ]
