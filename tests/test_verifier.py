import pathlib

from click.testing import CliRunner

from fme_packager.cli import verify

CWD = pathlib.Path(__file__).parent.resolve()


def test_verify_valid():
    runner = CliRunner()
    result = runner.invoke(verify, [str(CWD / "fixtures" / "example.my-package-0.1.0.fpkg")])
    assert result.exit_code == 0


def test_verify_invalid():
    runner = CliRunner()
    result = runner.invoke(verify, [str(CWD / "fixtures" / "example.invalid-package-0.1.0.fpkg")])
    assert str(result.exception) == "MyInvalidGreeter is missing doc"


def test_verify_non_fpkg():
    runner = CliRunner()
    result = runner.invoke(verify, [str(CWD / "fixtures" / "valid_package/package.yml")])
    assert str(result.exception) == "The file must have a .fpkg extension"
