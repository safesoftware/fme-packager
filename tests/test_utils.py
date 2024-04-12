import os

import pytest

from fme_packager.utils import pipeline, chdir, keep_attributes


def test_pipeline():
    def add_one(x):
        return x + 1

    def multiply_by_two(x):
        return x * 2

    piped_functions = pipeline(add_one, multiply_by_two)

    assert list(piped_functions([1, 2, 3])) == [4, 6, 8]


def test_empty_pipeline():
    piped_functions = pipeline()

    assert list(piped_functions([1, 2, 3])) == [1, 2, 3]


def test_chdir(tmp_path):
    old_dir = os.getcwd()

    new_dir = tmp_path / "new_dir"
    new_dir.mkdir()

    with chdir(new_dir):
        assert os.getcwd() == str(new_dir)

    assert os.getcwd() == old_dir


@pytest.mark.parametrize(
    "test_dict, attributes, expected",
    [
        ({"a": 1, "b": 2, "c": 3}, ["a", "b"], {"a": 1, "b": 2}),
        ({"a": 1, "b": 2, "c": 3}, ["c"], {"c": 3}),
        ({"a": 1, "b": 2, "c": 3}, ["d"], {}),
    ],
)
def test_keep_attributes(test_dict, attributes, expected):
    assert keep_attributes(test_dict, *attributes) == expected
