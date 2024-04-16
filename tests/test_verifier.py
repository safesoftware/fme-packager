import pathlib

import pytest
from click.testing import CliRunner

from fme_packager.cli import verify, pack

CWD = pathlib.Path(__file__).parent.resolve()


def test_verify_valid():
    runner = CliRunner()
    result = runner.invoke(
        verify, [str(CWD / "fixtures" / "fpkgs" / "example.my-package-0.1.0.fpkg")]
    )
    assert result.exit_code == 0
    assert "Success" in result.output


@pytest.mark.parametrize("package_name", ["valid_package", "fmxj_package"])
def test_pack_verify(package_name):
    runner = CliRunner()
    # create a fpkg
    result = runner.invoke(pack, [str(CWD / "fixtures" / package_name)])
    assert result.exit_code == 0

    # verify the built fpkg
    dist_dir = CWD / "fixtures" / package_name / "dist"
    result = runner.invoke(verify, [str(CWD / dist_dir / "example.my-package-0.1.0.fpkg")])
    assert result.exit_code == 0
    assert "Success" in result.output


@pytest.mark.parametrize("flags", [[], ["--json"], ["--verbose"], ["--json", "--verbose"]])
def test_verify_invalid(flags):
    runner = CliRunner()
    result = runner.invoke(
        verify, [str(CWD / "fixtures" / "fpkgs" / "example.invalid-package-0.1.0.fpkg"), *flags]
    )

    if "--json" in flags:
        assert '{"status": "error", "message": "MyInvalidGreeter is missing doc"}' in result.output
    else:
        assert "MyInvalidGreeter is missing doc" in result.output

    if "--verbose" in flags:
        assert "Working on transformer" in result.output
    else:
        assert "Working on transformer" not in result.output


def test_verify_non_fpkg():
    runner = CliRunner()
    result = runner.invoke(verify, [str(CWD / "fixtures" / "valid_package" / "package.yml")])
    assert "The file must exist and have a .fpkg extension" in result.output


def test_verify_non_existent():
    runner = CliRunner()
    result = runner.invoke(verify, [str(CWD / "fixtures" / "does-not-exist.fpkg")])
    assert "The file must exist and have a .fpkg extension" in result.output
