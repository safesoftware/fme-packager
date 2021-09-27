import json
import os

from ruamel.yaml import YAML


def load_fpkg_metadata(fpkg_path):
    with open(os.path.join(fpkg_path, "package.yml")) as f:
        return FMEPackageMetadata(YAML(typ="safe").load(f))


def load_metadata_json_schema():
    with open(os.path.join(os.path.dirname(__file__), "spec.json")) as f:
        return json.load(f)


class TransformerMetadata:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def name(self):
        return self.dict["name"]

    @property
    def version(self):
        return self.dict["version"]


class PythonPackageMetadata:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def name(self):
        return self.dict["name"]


class FormatMetadata:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def name(self):
        return self.dict["name"]


class WebServiceMetadata:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def name(self):
        return self.dict["name"]


class WebFilesystemMetadata:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def name(self):
        return self.dict["name"]


class Author:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def name(self):
        return self.dict["name"]

    @property
    def email(self):
        return self.dict["name"]


class FMEPackageMetadata:
    def __init__(self, metadata_dict):
        self.dict = metadata_dict

    @property
    def fpkg_version(self):
        return self.dict["fpkg_version"]

    @property
    def uid(self):
        return self.dict["uid"]

    @property
    def publisher_uid(self):
        return self.dict["publisher_uid"]

    @property
    def name(self):
        return self.dict["name"]

    @property
    def description(self):
        return self.dict["description"]

    @property
    def version(self):
        return self.dict["version"]

    @property
    def minimum_fme_build(self):
        return self.dict["minimum_fme_build"]

    @property
    def author(self):
        return Author(self.dict["author"])

    @property
    def package_content(self):
        return self.dict.get("package_content", {})

    @property
    def transformers(self):
        return [
            TransformerMetadata(item)
            for item in self.package_content.get("transformers", [])
        ]

    @property
    def python_packages(self):
        return [
            PythonPackageMetadata(item)
            for item in self.package_content.get("python_packages", [])
        ]

    @property
    def formats(self):
        return [
            FormatMetadata(item) for item in self.package_content.get("formats", [])
        ]

    @property
    def web_services(self):
        return [
            WebServiceMetadata(item)
            for item in self.package_content.get("web_services", [])
        ]

    @property
    def web_filesystems(self):
        return [
            WebFilesystemMetadata(item)
            for item in self.package_content.get("web_filesystems", [])
        ]
