import os
from collections import namedtuple
from pathlib import Path


def split_fpkg_filename(filename):
    """
    Split a filename of the form `A.B-C.fpkg`.

    :param filename: Filename to split.
    :raises ValueError: If filename doesn't end in "fpkg", or any resulting value is empty.
    :return: publisher_uid, package_uid, version.
        These values aren't validated, but are guaranteed to not be empty.
    """
    name, _, extension = filename.partition(".")
    if extension != "fpkg":
        raise ValueError("FME Package extension must be 'fpkg', not '{}'".format(extension))
    publisher_uid, _, right = name.partition(".")
    package_uid, _, version = right.rpartition("-")
    if not publisher_uid or not package_uid or not version:
        raise ValueError("Unrecognized fpkg name '{}'".format(name))
    return publisher_uid, package_uid, version


def build_fpkg_filename(publisher_uid, package_uid, version):
    """
    Build an fpkg filename. Inputs aren't validated, but must not be empty.

    :return: Assembled fpkg filename.
    """
    if not publisher_uid or not package_uid or not version:
        raise ValueError("All parts of the fpkg filename are required")
    return "{}.{}-{}.fpkg".format(publisher_uid, package_uid, version)


FORMATINFO_HDR = "FORMAT_NAME|FORMAT_LONG_NAME|DATASET_TYPE|DIRECTION|AUTOMATED_TRANSLATION_FLAG|COORDSYS_AWARE|FILTER|FORMAT_TYPE|USE_NATIVE_SPATIAL_INDEX|SOURCE_SETTINGS|DESTINATION_SETTINGS|VISIBLE|MIN_VERSION|MAX_VERSION|FORMAT_FAMILY|HAS_SIDECARS|MARKETING_FAMILY|FORMAT_CATEGORIES"
FormatInfo = namedtuple("FormatInfo", FORMATINFO_HDR.replace("|", " "), defaults=[""])
OPTIONAL_FORMATINFO_COLUMNS = ["FORMAT_CATEGORIES"]


def parse_formatinfo(line) -> FormatInfo:
    """
    Parse format info line with the FORMATINFO_HDR.

    :param str line: raw format info.
    :return: Parsed format into a FormatInfo named tuple.
    """
    num_columns = len(FORMATINFO_HDR.split("|"))
    num_required_columns = num_columns - len(OPTIONAL_FORMATINFO_COLUMNS)
    parts = line.strip().split("|")
    if len(parts) not in [num_columns, num_required_columns]:
        raise ValueError(
            "FormatInfo has {} elements, but expects at least {}".format(
                len(parts), num_required_columns
            )
        )
    return FormatInfo(*parts)


# Matches files that should not automatically be copied into an fpkg.
# Some of these are OS-specific metadata.
# FME file extensions are here because their copy over is gated by validation.
TREE_COPY_IGNORE_GLOBS = [
    ".*",
    "*.mclog",
    "*.flali",
    "*.fmf",
    "*.fmx",
    "*.db",
    "*.fms",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
]


def valid_fpkg_file(fpkg_file: str) -> str:
    """
    Validate that the file has the correct extension and exists
    """
    if not fpkg_file.lower().endswith(".fpkg") or not os.path.exists(fpkg_file):
        raise ValueError("The file must exist and have a .fpkg extension")

    return fpkg_file


def zip_filename_for_fpkg(directory: str, fpkg_file: str) -> Path:
    """
    Generate a zip file path
    """
    return Path(directory) / os.path.basename(fpkg_file[:-5] + ".zip")
