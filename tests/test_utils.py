import os

from fme_packager.utils import chdir


def test_chdir(tmp_path):
    old_dir = os.getcwd()

    new_dir = tmp_path / "new_dir"
    new_dir.mkdir()

    with chdir(new_dir):
        assert os.getcwd() == str(new_dir)

    assert os.getcwd() == old_dir
