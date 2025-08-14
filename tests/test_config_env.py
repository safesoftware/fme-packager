"""
Tests for the `fme-packager config-env` command.
"""

import sys

import pytest
from click.testing import CliRunner

from fme_packager.cli import config_env


def invoke(*args):
    args = args or []
    runner = CliRunner()
    return runner.invoke(config_env, args)


# Note that if FME_HOME is not set and the user is prompted for it,
# the prompt loops until a valid path is provided.


def test_fme_home_invalid_path():
    result = invoke("--fme-home", "/non/existent/path")
    assert (
        "Invalid value for '--fme-home': Directory '/non/existent/path' does not exist."
        in result.output
    )


def test_fme_home_no_exe():
    result = invoke("--fme-home", ".")
    assert "does not contain an FME executable" in result.output


leaf_dir = f"python{sys.version_info.major}{sys.version_info.minor}"


@pytest.mark.parametrize(
    "also_touch",
    [
        None,
        f"fmeobjects/{leaf_dir}/fmeobjects.pyd",
        f"python/fme-plugins-py{sys.version_info.major}{sys.version_info.minor}.zip",
    ],
)
def test_outputs(tmp_path, also_touch):
    """
    Test that fme_env.pth and fme_env.py are created with expected contents.
    """
    fme_home = tmp_path / "MOCK_FME"
    fme_home.mkdir(exist_ok=True)
    (fme_home / "fme.exe").touch()

    if also_touch:
        also_touch = fme_home / also_touch
        also_touch.parent.mkdir(parents=True)
        also_touch.touch()

    site_packages = tmp_path / "mock-site-packages"
    site_packages.mkdir(exist_ok=True)

    result = invoke(
        "--fme-home", fme_home.as_posix(), "--site-packages-dir", site_packages.as_posix()
    )
    assert result.exit_code == 0
    assert (site_packages / "fme_env.py").is_file()
    pth = (site_packages / "fme_env.pth").read_text().split()
    assert pth[-2:] == ["import", "fme_env"]
    pth = pth[:-2]  # Remove import statement for checking paths
    assert pth[0] == f"#{fme_home.as_posix()}"
    assert pth[1] == (fme_home / "python").as_posix()
    assert pth[2] == (fme_home / "python" / leaf_dir).as_posix()

    if not also_touch:
        assert len(pth) == 3
    elif "fmeobjects" in str(also_touch.parent):
        assert also_touch.parent.as_posix() in pth  # omit fake pyd
    elif also_touch.suffix == ".zip":
        assert also_touch.as_posix() in pth
