import json
import os
import shutil
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import Iterable, List

import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from fme_packager.operations import valid_fpkg_file, zip_filename_for_fpkg, parse_formatinfo
from fme_packager.packager import _load_format_line
from fme_packager.transformer import load_transformer, TransformerFile, Transformer
from fme_packager.utils import chdir
from fme_packager.web_service import _web_service_path, _parse_web_service


def _unpack_fpkg_file(directory: str, fpkg_file: str):
    """
    Unpack the FME Package file.

    :param directory: The directory where the FME Package file will be unpacked.
    :param fpkg_file: The FME Package file to be unpacked.
    :return: The directory where the FME Package file was unpacked.
    """
    valid_fpkg = valid_fpkg_file(fpkg_file)
    zip_file = zip_filename_for_fpkg(directory, valid_fpkg)
    shutil.copy(valid_fpkg, zip_file)
    shutil.unpack_archive(zip_file, directory)

    return directory


def _manifest_path(fpkg_dir: str) -> Path:
    """
    Return the manifest file.

    :param fpkg_dir: The directory where the FME Package file was unpacked.
    :return: The path to the manifest file.
    """
    return Path(fpkg_dir) / "package.yml"


def _parsed_manifest(yaml_file: Path) -> dict:
    """
    Parse the manifest file.

    :param yaml_file: The path to the manifest yaml file.
    :return: A dictionary of the parsed YAML.
    """
    with open(yaml_file, "r") as file:
        return yaml.safe_load(file)


TransformerFilenames = namedtuple(
    "TransformerFilenames", ["filename", "readme_filename"], defaults=[None, None]
)

FormatFilenames = namedtuple(
    "FormatFilenames", ["filename", "readme_filename", "db_filename"], defaults=[None, None, None]
)


def _transformer_filenames(transformer_name: str) -> TransformerFilenames:
    """
    Retrieve filenames for the transformer and its readme

    Input dict must have the key:
    - 'name': The name of the transformer.

    :param transformer_name: The name of the transformer to retrieve filenames for.
    :return: A tuple containing the filename and readme filename.
    """
    if not transformer_name:
        return TransformerFilenames(filename=None, readme_filename=None)

    result = dict()
    for ext, key in [("fmx", "filename"), ("fmxj", "filename"), ("md", "readme_filename")]:
        potential_filename = str(Path("transformers") / f"{transformer_name}.{ext}")
        if os.path.exists(potential_filename):
            result[key] = potential_filename

    return TransformerFilenames(**result)


def _format_filenames(format_name: str) -> FormatFilenames:
    """
    Retrieve filenames for the format and its readme

    :param format_name: The name of the format to retrieve filenames for.
    :return: A tuple containing the filename, db filename and readme filename.
    """
    if not format_name:
        return FormatFilenames(filename=None, readme_filename=None, db_filename=None)

    filenames = {
        "filename": str(Path("formats") / f"{format_name}.fmf"),
        "db_filename": str(Path("formats") / f"{format_name}.db"),
        "readme_filename": str(Path("formats") / f"{format_name}.md"),
    }

    for key, filename in filenames.items():
        if not os.path.exists(filename):
            filenames[key] = None

    return FormatFilenames(**filenames)


def _transformer_data(loaded_file: TransformerFile) -> dict:
    """
    Get the relevant data from the loaded transformer file.

    Output dict will have the following keys:
    - 'versions': A list of dictionaries, each containing:
        - 'name': The name of the transformer.
        - 'version': The version number of the transformer.
        - 'categories': The categories of the transformer.
        - 'aliases': The aliases of the transformer.
        - 'visible': The visibility status of the transformer.

    :param loaded_file: The loaded transformer file.
    :return: The updates for the transformer dictionary.
    """
    versions: list[Transformer] = loaded_file.versions()
    return {
        "versions": [
            {
                "name": version.name,
                "version": version.version,
                "categories": version.categories,
                "aliases": version.aliases,
                "visible": version.visible,
            }
            for version in versions
        ],
    }


def _content_description(readme_filename: str) -> dict:
    """
    Get the description of the transformer or format from the readme file.

    Output dict will have keys:
    - 'description': The description of the transformer or format.
    - 'description_format': The format of the description either 'md', 'text', or 'html'.

    :param readme_filename: The filename of the readme file.
    :return: The update for the transformer or format dictionary.
    """
    try:
        with open(readme_filename, "r") as file:
            return {
                "description": file.read(),
                "description_format": "md",
            }
    except OSError:
        return {
            "description": None,
            "description_format": None,
        }


def _get_all_categories(transformers: Iterable[dict], formats: Iterable[dict]) -> List[str]:
    """
    Get the union of all the categories from the transformers.

    :param transformers: An iterable of transformer dicts
    :return: An alphabetically sorted list of all categories from the transformers.
    """
    all_categories = set()
    for transformer in transformers:
        if not transformer.get("versions", None):
            continue
        highest_version = max(
            transformer["versions"], key=lambda transformer_version: transformer_version["version"]
        )
        if not highest_version["categories"]:
            continue
        all_categories.update(highest_version["categories"])

    for format in formats:
        if not format.get("categories", None):
            continue
        all_categories.update(format["categories"])

    all_categories_list = list(all_categories)
    all_categories_list.sort()
    return all_categories_list


def _enhance_transformer_info(transformers: Iterable[dict]) -> Iterable[dict]:
    """
    Enhance the transformer entries in the manifest with additional information.

    :param transformers: An iterable of transformer dicts
    :return: An iterable of transformer dicts with enhanced information
    """
    if not transformers:
        return []

    for transformer in transformers:
        filenames = _transformer_filenames(transformer["name"])
        loaded_transformer = load_transformer(filenames.filename)
        transformer.update(_transformer_data(loaded_transformer))
        transformer.update(_content_description(filenames.readme_filename))
        transformer["latest_version"] = transformer.pop("version")

    return transformers


def _enhance_web_service_info(web_services: Iterable[dict]) -> Iterable[dict]:
    """
    Enhance the web service entries in the manifest with additional information.

    :param web_services: An iterable of web service dicts
    :return: An iterable of web service dicts with enhanced information
    """
    if not web_services:
        return []

    for web_service in web_services:
        web_service_path = _web_service_path(web_service["name"])
        web_service_content = _parse_web_service(web_service_path)
        web_service.update(web_service_content)

    return web_services


def _to_bool(value: str) -> bool:
    """
    Convert a string to a boolean.

    :param value: The value to convert.
    :return: The boolean value.
    """
    return value.upper() == "YES"


def _format_data(format_line: str) -> dict:
    """
    Get the relevant data from the loaded format file.

    Output dict will have the following keys:
    - 'visible': The visibility status of the format.
    - 'fds_info': The FDS info line of the format.
    - 'categories': The categories of the format.

    :param format_line: The loaded format line.
    :return: The updates for the format dictionary.
    """

    format_info = parse_formatinfo(format_line)
    format_data = {"visible": None, "fds_info": None, "categories": None}

    if format_info:
        format_data["fds_info"] = format_line
        format_data["visible"] = _to_bool(format_info.VISIBLE)
        format_data["categories"] = (
            format_info.FORMAT_CATEGORIES.split(",") if format_info.FORMAT_CATEGORIES else []
        )

    return format_data


def _enhance_format_info(publisher_uid: str, uid: str, formats: Iterable[dict]) -> Iterable[dict]:
    """
    Enhance the format entries in the manifest with additional information.

    :param publisher_uid: The publisher UID
    :param uid: The UID
    :param formats: An iterable of format dicts
    :return: An iterable of format dicts with enhanced information
    """
    if not formats:
        return []

    for format in formats:
        filenames = _format_filenames(format["name"])
        format_data = _format_data(_load_format_line(filenames.db_filename))
        format["short_name"] = format["name"]
        format["name"] = f"{publisher_uid}.{uid}.{format['name']}"
        format.update(_content_description(filenames.readme_filename))
        format.update(format_data)

    return formats


def _load_output_schema() -> dict:
    """
    Load the output schema for the summarizer in jsonschema format.

    :return: The output schema.
    """
    with open(Path(__file__).parent / "summarizer_spec.json", "r") as file:
        return json.load(file)


def summarize_fpkg(fpkg_path: str) -> str:
    """
    Summarize the FME Package.

    The output conforms to summarizer_spec.json.

    :param fpkg_path: The path to the FME Package.
    :return: A JSON string of the summarized FME Package, or an error message under the key 'error'.
    """
    output_schema = _load_output_schema()

    with tempfile.TemporaryDirectory() as temp_dir:
        _unpack_fpkg_file(temp_dir, fpkg_path)

        with chdir(temp_dir):
            manifest = _parsed_manifest(_manifest_path(temp_dir))
            transformers = manifest.get("package_content", {}).get("transformers", [])
            formats = manifest.get("package_content", {}).get("formats", [])
            web_services = manifest.get("package_content", {}).get("web_services", [])
            manifest["package_content"] = manifest.get("package_content", {})
            manifest["package_content"]["transformers"] = _enhance_transformer_info(transformers)
            manifest["package_content"]["formats"] = _enhance_format_info(
                manifest.get("publisher_uid", ""), manifest.get("uid", ""), formats
            )
            manifest["package_content"]["web_services"] = _enhance_web_service_info(web_services)
            manifest["categories"] = _get_all_categories(transformers, formats)
        try:
            validate(manifest, output_schema)
        except ValidationError as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"The generated output did not conform to the schema: {e.message}",
                },
                indent=2,
            )

        return json.dumps(manifest, indent=2)
