import pathlib

import pytest

from fme_packager.help import HelpBuilder, get_expected_help_index, MIN_BUILD_WITH_URL_SUPPORT
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
    assert get_expected_help_index(mock_metadata) == {
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
    assert get_expected_help_index(metadata) == {
        "ft_example_package_hyphen_demoformat_param_r": "/demoformat_ft_param_r.htm",
        "ft_example_package_hyphen_demoformat_param_w": "/demoformat_ft_param_w.htm",
        "ft_example_package_hyphen_demoformat_user_attr": "/demoformat_ft_user_attr.htm",
        "param_example_package_hyphen_demoformat_r": "/demoformat_param_r.htm",
        "param_example_package_hyphen_demoformat_w": "/demoformat_param_w.htm",
        "rw_example_package_hyphen_demoformat_feature_rep": "/demoformat_feature_rep.htm",
        "rw_example_package_hyphen_demoformat_index": "/demoformat.htm",
    }
    assert sorted(get_expected_help_index(metadata)) == [
        "ft_example_package_hyphen_demoformat_param_r",
        "ft_example_package_hyphen_demoformat_param_w",
        "ft_example_package_hyphen_demoformat_user_attr",
        "param_example_package_hyphen_demoformat_r",
        "param_example_package_hyphen_demoformat_w",
        "rw_example_package_hyphen_demoformat_feature_rep",
        "rw_example_package_hyphen_demoformat_index",
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
    assert sorted(get_expected_help_index(metadata, read_only)) == [
        "ft_example_package_demoformat_param_r",
        "ft_example_package_demoformat_user_attr",
        "param_example_package_demoformat_r",
        "rw_example_package_demoformat_feature_rep",
        "rw_example_package_demoformat_index",
    ]
    assert sorted(get_expected_help_index(metadata, write_only)) == [
        "ft_example_package_demoformat_param_w",
        "ft_example_package_demoformat_user_attr",
        "param_example_package_demoformat_w",
        "rw_example_package_demoformat_feature_rep",
        "rw_example_package_demoformat_index",
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


@pytest.mark.parametrize(
    "minimum_build, csv_content, expected_error",
    [
        # Case 1: FME build < MIN_BUILD_WITH_URL_SUPPORT, fallback required for URLs
        (
            23224,
            """\
fmx_example_package-hyphen_Transformer,http://example.com
fmx_example_package-hyphen_Transformer,/Transformers/Transformer-pkg.htm
""",
            None,
        ),
        # Case 2: FME build >= MIN_BUILD_WITH_URL_SUPPORT, URLs allowed without fallback
        (
            MIN_BUILD_WITH_URL_SUPPORT,
            """\
fmx_example_package-hyphen_Transformer,http://example.com
""",
            None,
        ),
        # Case 3: FME build <= MIN_BUILD_WITH_URL_SUPPORT, single local path allowed
        (
            23224,
            """\
fmx_example_package-hyphen_Transformer,/Transformers/Transformer-pkg.htm
""",
            None,
        ),
        # Validation failure: Missing fallback for FME build < MIN_BUILD_WITH_URL_SUPPORT
        (
            23224,
            """\
fmx_example_package-hyphen_Transformer,http://example.com
""",
            "Minimum build required for URL support is",
        ),
        # Validation failure: Invalid structure in CSV
        (
            MIN_BUILD_WITH_URL_SUPPORT,
            """\
fmx_example_package-hyphen_Transformer,http://example.com
fmx_example_package-hyphen_Transformer,/Transformers/Transformer-pkg.htm
fmx_example_package-hyphen_Transformer,/Transformers/Transformer-pkg.htm
""",
            "Invalid entries for",
        ),
    ],
)
def test_validate_index(tmp_path, minimum_build, csv_content, expected_error):
    metadata = FMEPackageMetadata(
        {
            "uid": "package-hyphen",
            "publisher_uid": "example",
            "minimum_fme_build": minimum_build,
            "package_content": {"transformers": [{"name": "Transformer", "version": 1}]},
        }
    )
    help_builder = HelpBuilder(metadata, HELP_FIXTURES_DIR / "htm", tmp_path, {})
    help_builder.build()

    # Create the package_help.csv file
    csv_file = tmp_path / "package_help.csv"
    csv_file.write_text(csv_content)

    if expected_error:
        with pytest.raises(ValueError, match=expected_error):
            help_builder.validate_index(tmp_path)
    else:
        help_builder.validate_index(tmp_path)
