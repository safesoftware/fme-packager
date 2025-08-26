"""
Tools for generating a JSON summary of an FME Package's contents.
The output is an extension of what's in metadata.yml,
with additional properties surfaced from the package's contents.
The output is for FME Hub's use, and conforms to summarizer_spec.json.
"""

import json
import os
import tempfile
from collections import namedtuple
from importlib.resources import open_text
from pathlib import Path
from typing import Iterable, List, Union

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from fme_packager.operations import parse_formatinfo, extract_fpkg, load_format_line
from fme_packager.transformer import load_transformer, TransformerFile
from fme_packager.web_service import _web_service_path, _parse_web_service
from fme_packager.metadata import (
    FormatMetadata,
    WebServiceMetadata,
    TransformerMetadata,
    load_fpkg_metadata,
)


TransformerFilenames = namedtuple(
    "TransformerFilenames", ["filename", "readme_filename"], defaults=[None, None]
)

FormatFilenames = namedtuple(
    "FormatFilenames", ["filename", "readme_filename", "db_filename"], defaults=[None, None, None]
)


class Summarizer:
    def __init__(self, base_dir: Union[Path, str]):
        self.base_dir: Path = Path(base_dir)

    def transformer_filenames(self, transformer_name: str) -> TransformerFilenames:
        """
        Retrieve filenames for the transformer and its readme

        :param transformer_name: The name of the transformer to retrieve filenames for.
        :return: A tuple containing the filename and readme filename.
        """
        if not transformer_name:
            return TransformerFilenames(filename=None, readme_filename=None)

        result: dict = {}
        for ext, key in [("fmx", "filename"), ("fmxj", "filename"), ("md", "readme_filename")]:
            potential_path = self.base_dir / "transformers" / f"{transformer_name}.{ext}"
            if potential_path.exists():
                result[key] = potential_path.as_posix()

        return TransformerFilenames(**result)

    def format_filenames(self, format_name: str) -> FormatFilenames:
        """
        Retrieve filenames for the format and its readme

        :param format_name: The name of the format to retrieve filenames for.
        :return: A tuple containing the filename, db filename, and readme filename.
        """
        if not format_name:
            return FormatFilenames(filename=None, readme_filename=None, db_filename=None)

        filenames = {
            "filename": (self.base_dir / "formats" / f"{format_name}.fmf").as_posix(),
            "db_filename": (self.base_dir / "formats" / f"{format_name}.db").as_posix(),
            "readme_filename": (self.base_dir / "formats" / f"{format_name}.md").as_posix(),
        }

        for key, filename in filenames.items():
            if not Path(filename).exists():
                filenames[key] = None

        return FormatFilenames(**filenames)

    def enhance_transformer_info(
        self, transformers: Iterable[TransformerMetadata]
    ) -> Iterable[dict]:
        """
        Enhance the transformer entries in the manifest with additional information.

        :return: An iterable of transformer dicts with enhanced information
        """
        result = []
        for tm in transformers:
            filenames = self.transformer_filenames(tm.name)
            loaded_transformer = load_transformer(filenames.filename)
            entry = {
                "name": tm.name,
                "latest_version": tm.version,
            }
            entry.update(_transformer_data(loaded_transformer))
            entry.update(_content_description(filenames.readme_filename))
            result.append(entry)

        return result

    def enhance_web_service_info(
        self, web_services: Iterable[WebServiceMetadata]
    ) -> Iterable[dict]:
        """
        Enhance the web service entries in the manifest with additional information.

        :return: An iterable of web service dicts with enhanced information
        """
        result = []
        for ws in web_services:
            ws_name = ws.name
            web_service_path = self.base_dir / _web_service_path(ws_name)
            web_service_content = _parse_web_service(web_service_path)
            # Normalize name without .xml suffix
            normalized_name = ws_name[:-4] if ws_name.endswith(".xml") else ws_name

            entry = {"name": normalized_name}
            for key in [
                "help_url",
                "description",
                "markdown_description",
                "connection_description",
                "markdown_connection_description",
            ]:
                entry[key] = web_service_content.get(key, "") or ""
            result.append(entry)

        return result

    def enhance_format_info(
        self, publisher_uid: str, uid: str, formats: Iterable[FormatMetadata]
    ) -> Iterable[dict]:
        """
        Enhance the format entries in the manifest with additional information.

        :return: iterable of format dicts with enhanced information
        """
        result = []
        for fm in formats:
            short_name = fm.name
            filenames = self.format_filenames(short_name)
            format_data = _format_data(load_format_line(filenames.db_filename))
            entry: dict = {
                "short_name": short_name,
                "name": f"{publisher_uid}.{uid}.{short_name}",
            }
            entry.update(_content_description(filenames.readme_filename))
            entry.update(format_data)
            result.append(entry)

        return result


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
        - 'data_processing_types': The data processing types of the transformer.

    :param loaded_file: The loaded transformer file.
    :return: The updates for the transformer dictionary.
    """
    return {
        "versions": [
            {
                "name": version.name,
                "version": version.version,
                "categories": version.categories,
                "aliases": version.aliases,
                "visible": version.visible,
                "data_processing_types": version.data_processing_types,
            }
            for version in loaded_file.versions()
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

    for fmt in formats:
        if not fmt.get("categories", None):
            continue
        all_categories.update(fmt["categories"])

    all_categories_list = list(all_categories)
    all_categories_list.sort()
    return all_categories_list


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
    if format_info := parse_formatinfo(format_line):
        return {
            "fds_info": format_line,
            "visible": format_info.VISIBLE.upper() != "NO",
            "categories": (
                format_info.FORMAT_CATEGORIES.split(",") if format_info.FORMAT_CATEGORIES else []
            ),
        }

    return {"visible": None, "fds_info": None, "categories": None}


def _load_output_schema() -> dict:
    """
    Load the output schema for the summarizer in jsonschema format.

    :return: The output schema.
    """
    with open_text("fme_packager", "summarizer_spec.json") as f:
        return json.load(f)


def package_deprecated(transformers: Iterable[dict], formats: Iterable[dict]) -> bool:
    """
    Determine if the package is deprecated based on its contents.
    If the package contains transformers or formats, and the highest version of all transformers are not visible,
    and if all formats are not visible, then the package is deprecated.

    :param transformers: An iterable of transformer dicts
    :param formats: An iterable of format dicts
    :return: True if the package is deprecated, False otherwise.
    """
    if not transformers and not formats:
        return False

    is_transformer_visible = any(
        max(transformer["versions"], key=lambda v: v["version"]).get("visible", True)
        for transformer in transformers
        if transformer.get("versions")
    )

    is_format_visible = any(f.get("visible", True) for f in formats)

    return not (is_transformer_visible or is_format_visible)


def summarize_fpkg(fpkg_path: Union[str, os.PathLike]) -> dict:
    """
    Summarize the FME Package.

    The output conforms to summarizer_spec.json.

    :param fpkg_path: The path to the FME Package file (.fpkg) or an already extracted package directory.
    :return: A dict summary of the FME Package, or an error dict with keys 'status' and 'message'.
    """
    input_path = Path(fpkg_path)

    # Always create a temp directory to simplify logic; only used when input is an .fpkg file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        if input_path.is_dir():
            working_dir = input_path
        else:
            extract_fpkg(input_path, temp_dir)
            working_dir = temp_dir

        metadata = load_fpkg_metadata(working_dir)
        manifest = metadata.dict.copy()
        ctx = Summarizer(working_dir)

        manifest["package_content"] = metadata.package_content
        manifest["package_content"]["transformers"] = ctx.enhance_transformer_info(
            metadata.transformers
        )
        manifest["package_content"]["formats"] = ctx.enhance_format_info(
            metadata.publisher_uid, metadata.uid, metadata.formats
        )
        manifest["package_content"]["web_services"] = ctx.enhance_web_service_info(
            metadata.web_services
        )
        manifest["categories"] = _get_all_categories(
            manifest["package_content"]["transformers"], manifest["package_content"]["formats"]
        )
        manifest["deprecated"] = package_deprecated(
            manifest["package_content"]["transformers"], manifest["package_content"]["formats"]
        )

    try:
        validate(manifest, _load_output_schema())
    except ValidationError as e:
        return {
            "status": "error",
            "message": f"The generated output did not conform to the schema: {e.message}",
        }

    return manifest
