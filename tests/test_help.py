import pathlib

import pytest

from fme_packager.help import HelpBuilder, get_expected_help_index
from fme_packager.metadata import FMEPackageMetadata

CWD = pathlib.Path(__file__).parent.resolve()
HELP_FIXTURES_DIR = CWD / "fixtures" / "help"


@pytest.fixture
def mock_metadata():
    return FMEPackageMetadata(
        {
            "uid": "package-hyphen",
            "publisher_uid": "example",
            "minimum_fme_build": 23224,
            "package_content": {"transformers": [{"name": "Transformer", "version": 1}]},
        }
    )


def test_get_expected_help_contexts_transformer(mock_metadata):
    assert get_expected_help_index(mock_metadata)[0] == {
        "fmx_example_package-hyphen_Transformer": "/Transformer.htm"
    }


def test_get_expected_help_contexts_format():
    metadata = FMEPackageMetadata(
        {
            "uid": "package-hyphen",
            "publisher_uid": "example",
            "package_content": {"formats": [{"name": "demoformat"}]},
        }
    )
    assert get_expected_help_index(metadata)[0] == {
        "ft_example_package_hyphen_demoformat_param_r": "/demoformat_ft_param_r.htm",
        "ft_example_package_hyphen_demoformat_param_w": "/demoformat_ft_param_w.htm",
        "ft_example_package_hyphen_demoformat_user_attr": "/demoformat_ft_user_attr.htm",
        "param_example_package_hyphen_demoformat_r": "/demoformat_param_r.htm",
        "param_example_package_hyphen_demoformat_w": "/demoformat_param_w.htm",
        "rw_example_package_hyphen_demoformat_feature_rep": "/demoformat_feature_rep.htm",
        "rw_example_package_hyphen_demoformat_index": "/demoformat.htm",
    }
    assert get_expected_help_index(metadata)[1] == {
        "rw_example_package_hyphen_demoformat_quickfacts": "/demoformat_quickfacts.htm",
    }
    assert sorted(get_expected_help_index(metadata)[0]) == [
        "ft_example_package_hyphen_demoformat_param_r",
        "ft_example_package_hyphen_demoformat_param_w",
        "ft_example_package_hyphen_demoformat_user_attr",
        "param_example_package_hyphen_demoformat_r",
        "param_example_package_hyphen_demoformat_w",
        "rw_example_package_hyphen_demoformat_feature_rep",
        "rw_example_package_hyphen_demoformat_index",
    ]
    assert sorted(get_expected_help_index(metadata)[1]) == [
        "rw_example_package_hyphen_demoformat_quickfacts",
    ]


def test_get_expected_help_contexts_format_one_dir():
    metadata = FMEPackageMetadata(
        {
            "uid": "package",
            "publisher_uid": "example",
            "package_content": {"formats": [{"name": "demoformat"}]},
        }
    )
    read_only = {"demoformat": "r"}
    write_only = {"demoformat": "w"}
    assert sorted(get_expected_help_index(metadata, read_only)[0]) == [
        "ft_example_package_demoformat_param_r",
        "ft_example_package_demoformat_user_attr",
        "param_example_package_demoformat_r",
        "rw_example_package_demoformat_feature_rep",
        "rw_example_package_demoformat_index",
    ]
    assert sorted(get_expected_help_index(metadata, write_only)[0]) == [
        "ft_example_package_demoformat_param_w",
        "ft_example_package_demoformat_user_attr",
        "param_example_package_demoformat_w",
        "rw_example_package_demoformat_feature_rep",
        "rw_example_package_demoformat_index",
    ]
    assert sorted(get_expected_help_index(metadata, read_only)[1]) == [
        "rw_example_package_demoformat_quickfacts",
    ]


def test_htm(mock_metadata, tmp_path):
    maker = HelpBuilder(mock_metadata, HELP_FIXTURES_DIR / "htm", tmp_path, {})
    maker.build()
    assert (tmp_path / "Transformers" / "Transformer-pkg.htm").is_file()
    assert (tmp_path / "package_help.csv").is_file()


def test_md(mock_metadata, tmp_path):
    maker = HelpBuilder(mock_metadata, HELP_FIXTURES_DIR / "md", tmp_path, {})
    maker.build()
    assert not (tmp_path / "Transformer.md").is_file()
    html_file = tmp_path / "Transformer.htm"
    with html_file.open("r") as f:
        html = f.read()
        assert html.startswith("<!DOCTYPE html>")
        assert '<link rel="stylesheet" href="../../css/style.css" />' in html
        assert '<h1 class="fmx">' in html
        assert '<p><span class="TransformerSummary">' in html
    index_file = tmp_path / "package_help.csv"
    assert index_file.is_file()
    with index_file.open("r") as f:
        assert f.read() == "fmx_example_package-hyphen_Transformer,/Transformer.htm\n"
