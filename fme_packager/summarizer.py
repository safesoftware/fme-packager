import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

import yaml

from fme_packager.context import verbose_flag
from fme_packager.operations import valid_fpkg_file, zip_filename_for_fpkg
from fme_packager.transformer import load_transformer, TransformerFile, Transformer
from fme_packager.utils import pipeline, keep_attributes, chdir

_TRANSFORMER_ATTRIBUTES = ["name", "versions", "description", "description_format"]


def _unpack_fpkg_file(directory: str, fpkg_file: str):
    """
    Unpack the FME Package file
    """
    valid_fpkg = valid_fpkg_file(fpkg_file)
    zip_file = zip_filename_for_fpkg(directory, valid_fpkg)
    shutil.copy(valid_fpkg, zip_file)
    shutil.unpack_archive(zip_file, directory)

    return directory


def _manifest_path(fpkg_dir: str) -> Path:
    """
    Return the manifest file
    """
    return Path(fpkg_dir) / "package.yml"


def _parsed_manifest(yaml_file: Path) -> dict:
    """
    Parse the manifest file. The input is the path to the manifest yaml file. The output is a dictionary of the YAML.
    """
    with open(yaml_file, "r") as file:
        return yaml.safe_load(file)


def _add_transformer_filenames(transformer: dict) -> dict:
    """
    Add the filenames for the transformer and its readme to the transformer dictionary.

    Input dict must have the key:
    - 'name': The name of the transformer.

    Output dict will have the added keys:
    - 'filename': The filename of the transformer.
    - 'readme_filename': The filename of the transformer's readme.
    """
    transformer = transformer.copy()
    for ext, key in [("fmx", "filename"), ("fmxj", "filename"), ("md", "readme_filename")]:
        if 'name' not in transformer:
            continue
        potential_filename = str(Path("transformers") / f"{transformer['name']}.{ext}")
        if os.path.exists(potential_filename):
            transformer[key] = potential_filename

    return transformer


def _load_transformer(transformer: dict) -> dict:
    """
    Parse the transformer files and add the content to the transformer dictionary.

    Input dict must have the key:
    - 'filename': The filename of the transformer.

    Output dict will have the added keys:
    - 'loaded_file': The content of the transformer file, as a TransformerFile object
    """
    return {"loaded_file": load_transformer(transformer["filename"]), **transformer}


def _promote_transformer_data(transformer: dict) -> dict:
    """
    Promote the transformer data from the loaded file to the transformer dictionary.

    Input dict must have the key:
    - 'loaded_file': The content of the transformer file, as a TransformerFile object.

    Output dict will have the added keys:
    - 'name': The name of the transformer.
    - 'version': The version of the transformer.
    - 'category': The category of the transformer.
    - 'aliases': The aliases of the transformer.
    - 'replaced_by': The transformer that replaced this transformer.
    - 'changes': The changes made to the transformer.
    - 'deprecated': The deprecated status of the transformer.
    """
    loaded_file: TransformerFile = transformer["loaded_file"]
    versions: list[Transformer] = loaded_file.versions()
    transformer.update(
        {
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
    )

    return transformer


def _add_transformer_description(transformer: dict) -> dict:
    """
    Add the description to the transformer dictionary.

    Input dict must have the key:
    - 'readme_filename': The filename of the transformer's readme.

    Output dict will have the added keys:
    - 'description': The description of the transformer.
    - 'description_format': The format of the description.
    """
    try:
        with open(transformer.get("readme_filename"), "r") as file:
            transformer["description"] = file.read()
            transformer["description_format"] = "md"
    except OSError:
        pass

    return transformer


def _get_all_categories(transformers: Iterable[TransformerFile]) -> set[str]:
    """
    Get the union of all the categories from the transformers
    """
    all_categories = set()
    for transformer in transformers:
        transformer_versions = list(transformer.versions())
        if transformer_versions:
            # Find the version with the highest version number
            highest_version = max(
                transformer_versions, key=lambda transformer_version: transformer_version.version
            )
            if not highest_version.categories:
                continue
            all_categories.update(highest_version.categories)
    return all_categories


_enhance_transformer_info = pipeline(
    _add_transformer_filenames,
    _load_transformer,
    _promote_transformer_data,
    _add_transformer_description,
)


def summarize_fpkg(fpkg_path: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        _unpack_fpkg_file(temp_dir, fpkg_path)

        with chdir(temp_dir):
            manifest = _parsed_manifest(_manifest_path(temp_dir))
            transformers = list(
                _enhance_transformer_info(manifest["package_content"]["transformers"])
            )

            manifest["categories"] = list(
                _get_all_categories(t["loaded_file"] for t in transformers)
            )
            manifest["package_content"]["transformers"] = [
                keep_attributes(t, *_TRANSFORMER_ATTRIBUTES) for t in transformers
            ]

        return json.dumps(manifest, indent=2 if verbose_flag.get() else None)
