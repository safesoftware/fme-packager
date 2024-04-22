import json
import os
import shutil
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import Iterable, Set

import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from fme_packager.operations import valid_fpkg_file, zip_filename_for_fpkg
from fme_packager.transformer import load_transformer, TransformerFile, Transformer
from fme_packager.utils import chdir

_TRANSFORMER_ATTRIBUTES = ["name", "versions", "description", "description_format"]


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


def _transformer_description(readme_filename: str) -> dict:
    """
    Get the description of the transformer from the readme file.

    Output dict will have keys:
    - 'description': The description of the transformer.
    - 'description_format': The format of the description either 'md', 'text', or 'html'.

    :param readme_filename: The filename of the readme file.
    :return: The update for the transformer dictionary.
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


def _get_all_categories(transformers: Iterable[dict]) -> Set[str]:
    """
    Get the union of all the categories from the transformers.

    :param transformers: An iterable of transformer dicts
    :return: A set of all categories from the transformers.
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
    return all_categories


def _enhance_transformer_info(transformers: Iterable[dict]) -> Iterable[dict]:
    """
    Enhance the transformer entries in the manifest with additional information.

    :param transformers: An iterable of transformer dicts
    :return: An iterable of transformer dicts with enhanced information
    """
    for transformer in transformers:
        filenames = _transformer_filenames(transformer["name"])
        loaded_transformer = load_transformer(filenames.filename)
        transformer.update(_transformer_data(loaded_transformer))
        transformer.update(_transformer_description(filenames.readme_filename))
        transformer["latest_version"] = transformer.pop("version")


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
            transformers = manifest["package_content"]["transformers"]
            _enhance_transformer_info(transformers)

            manifest["categories"] = list(_get_all_categories(transformers))
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
