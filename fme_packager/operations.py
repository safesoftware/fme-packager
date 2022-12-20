from collections import namedtuple


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


FORMATINFO_HDR = "FORMAT_NAME|FORMAT_LONG_NAME|DATASET_TYPE|DIRECTION|AUTOMATED_TRANSLATION_FLAG|COORDSYS_AWARE|FILTER|FORMAT_TYPE|USE_NATIVE_SPATIAL_INDEX|SOURCE_SETTINGS|DESTINATION_SETTINGS|VISIBLE|MIN_VERSION|MAX_VERSION|FORMAT_FAMILY|HAS_SIDECARS|MARKETING_FAMILY"
FormatInfo = namedtuple("FormatInfo", FORMATINFO_HDR.replace("|", " "))


def parse_formatinfo(line):
    """
    Parse format info line with the FORMATINFO_HDR.

    :param str line: raw format info.
    :return: Parsed format into a FormatInfo named tuple.
    """
    parts = line.strip().split("|")
    if len(parts) != len(FORMATINFO_HDR.split("|")):
        print(line)
        raise ValueError(
            "FormatInfo has {} elements, but expects {}".format(
                len(parts), len(FORMATINFO_HDR.split("|"))
            )
        )
    return FormatInfo(*parts)


TRANSFORMER_HDR = "name version category guid insert_mode blocked_looping process_count process_group_by process_groups_ordered build_num preserves_attrs deprecated pyver"
NamedTransformerHeader = namedtuple("NamedTransformerHeader", TRANSFORMER_HDR.split())


def parse_custom_transformer_header(line):
    """
    Parses custom transformer header.

    :param str line: fmx line.
    :return: Parsed format into a NamedTransformerHeader named tuple.
    """
    fields = line.replace("# TRANSFORMER_BEGIN", "").strip().split(",")
    fields[1] = int(fields[1])  # version
    fields[9] = int(fields[9])  # build_num
    return NamedTransformerHeader(*fields[: len(NamedTransformerHeader._fields)])
