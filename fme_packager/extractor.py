import json
import os
from pathlib import Path
import shutil
import tempfile

import yaml

from fme_packager.context import verbose_flag
from fme_packager.operations import valid_fpkg_file
from fme_packager.utils import pipeline, keep_attributes, chdir, split_key_values

_TRANSFORMER_ATTRIBUTES = [
    "aliases",
    "categories",
    "changes",
    "deprecated",
    "description",
    "description_format",
    "name",
    "replaced_by",
    "version",
]


def _zip_filename_for_fpkg(directory: str, fpkg_file: str) -> Path:
    """
    Generate a zip file path
    """
    return Path(directory) / os.path.basename(fpkg_file[:-5] + ".zip")


def _unpack_fpkg_file(directory: str, fpkg_file: str):
    """
    Unpack the FME Package file
    """
    valid_fpkg = valid_fpkg_file(fpkg_file)
    zip_file = _zip_filename_for_fpkg(directory, valid_fpkg)
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
    for ext, key in [("fmx", "filename"), ("md", "readme_filename")]:
        transformer[key] = str(Path("transformers") / f"{transformer['name']}.{ext}")

    return transformer


def _add_transformer_contents(transformer: dict) -> dict:
    """
    Parse the transformer files and add the content to the transformer dictionary.

    Input dict must have the key:
    - 'filename': The filename of the transformer.

    Output dict will have the added keys:
    - The keys parsed from the transformer file.
    """
    return {**_parse_transformer(open(transformer["filename"]).read()), **transformer}


def _split_categories(transformer: dict) -> dict:
    """
    Split a transformer's categories by comma.

    Input dict must have the key:
    - 'category': The category of the transformer.

    Output dict will have the added key:
    - 'categories': The categories of the transformer, split by comma.
    """
    return split_key_values(transformer, ",", "category", "categories")


def _split_aliases(transformer: dict) -> dict:
    """
    Split a transformer's aliases by space.

    Input dict must have the key:
    - 'aliases': The aliases of the transformer.

    Output dict will have the added key:
    - 'aliases': The aliases of the transformer, split by space.
    """
    return split_key_values(transformer, " ", "aliases")


def _visible_to_deprecated(transformer: dict) -> dict:
    """
    Convert the visible yes/no value to deprecated boolean.

    Input dict must have the key:
    - 'visible': The visibility of the transformer.

    Output dict will have the added key:
    - 'deprecated': The deprecated status of the transformer.
    """
    return {"deprecated": transformer.get("visible", "yes").lower() != "yes", **transformer}


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


def _parse_transformer(content: str) -> dict:
    """
    Extract the transformer metadata from the transformer file
    """
    verbose = verbose_flag.get()
    detected_keys = set()

    lines = content.split("\n")
    result = {}
    change_log_started = False
    for line in lines:
        # Split line into code and comment, ignore the comment
        line, _, _ = line.partition("#")
        line = line.strip()

        # Ignore everything after TEMPLATE_START
        if line == "TEMPLATE_START":
            break

        # Handle CHANGE_LOG block
        if line == "CHANGE_LOG_START":
            change_log_started = True
            result["changes"] = ""
            continue
        elif line == "CHANGE_LOG_END":
            change_log_started = False
            continue
        if change_log_started:
            result["changes"] += line.rstrip() + "\n"
            continue

        # Parse key-value pairs where key is a single word
        if (
            ":" in line
            and line.split(":", 1)[0].strip().isidentifier()
            and " " not in line.split(":", 1)[0]
        ):
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip() or None
            result[key] = value
            if verbose:
                detected_keys.add(key)

    if verbose:
        name = result.get("transformer_name", "<unknown>")
        print(f"Detected keys in transformer '{name}': {detected_keys}")

    return result


def _get_all_categories(transformers: list[dict]) -> set[str]:
    """
    Get the union of all the categories from the transformers
    """
    all_categories = set()
    for transformer in transformers:
        all_categories.update(transformer["categories"])
    return all_categories


_enhance_transformer_info = pipeline(
    _add_transformer_filenames,
    _add_transformer_contents,
    _add_transformer_description,
    _split_categories,
    _split_aliases,
    _visible_to_deprecated,
    lambda t: keep_attributes(t, *_TRANSFORMER_ATTRIBUTES),
)


def summarize_fpkg(fpkg_path: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        _unpack_fpkg_file(temp_dir, fpkg_path)

        with chdir(temp_dir):
            manifest = _parsed_manifest(_manifest_path(temp_dir))
            transformers = list(_enhance_transformer_info(manifest["package_content"]["transformers"]))

            manifest["categories"] = list(_get_all_categories(transformers))
            manifest["package_content"]["transformers"] = transformers

        return json.dumps(manifest)
