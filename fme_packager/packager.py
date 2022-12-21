import csv
import imghdr
import os
import shutil
import tempfile
import warnings
import zipfile
from fnmatch import fnmatch
from pathlib import Path

import png
import xmltodict
from build import ProjectBuilder
from jsonschema import validate
from packaging import version

from fme_packager.exception import (
    TransformerPythonCompatError,
    CustomTransformerPythonCompatError,
)
from fme_packager.metadata import load_fpkg_metadata, load_metadata_json_schema, TransformerMetadata
from fme_packager.operations import (
    build_fpkg_filename,
    parse_formatinfo,
)
from fme_packager.transformer import load_transformer, CustomTransformer


def is_valid_python_compatibility(python_compat_version):
    """
    Checks for a valid python compatibility value.

    :param str python_compat_version: Python compatibility version
    :rtype: bool
    """
    minimum_requirement = "35"
    is_python_3 = python_compat_version.startswith("3")
    meets_minimum_requirements = False
    if is_python_3:
        meets_minimum_requirements = version.parse(python_compat_version) >= version.parse(
            minimum_requirement
        )
    return is_python_3 and meets_minimum_requirements


def check_exists_and_copy(src, dest):
    """
    Copy source contents to a source path.

    :raises ValueError: If the source path does not exist.
    :param src: The source path.
    :param dest: The destination path.
    """
    if not os.path.exists(src):
        raise ValueError("{} is required but does not exist".format(src))
    shutil.copy(src, dest)


def enforce_png(path, min_width=0, min_height=0, square=False):
    """
    Enforces the path is a valid PNG file and the PNG meets a minimum height and width requirement.

    :raises ValueError: If the PNG is invalid or does not meet the minimum requirements.
    :param path: Path to PNG file.
    :param min_width: The minimum width of the image.
    :param min_height: The minimum width of the image.
    :param square: Whether the image should be square.
    """
    filetype = imghdr.what(path)
    if filetype != "png":
        raise ValueError("{} must be PNG, not {}".format(path, filetype))
    width, height, _, _ = png.Reader(filename=path).read()
    if width < min_width or height < min_height:
        raise ValueError(
            "Min dimensions are {}x{}. {} is {}x{}".format(
                min_width, min_height, path, width, height
            )
        )
    if square and width != height:
        raise ValueError("{} must be square".format(path))


def fq_format_short_name(publisher_uid, package_uid, format_name):
    """
    Formats the publisher_uid, package_uid and format_name

    :param publisher_uid: The Publisher unique identifier.
    :param package_uid: The package unique identifier.
    :param format_name: The format name.
    :return: publisher_uid, package_uid, format_name dot delimited and upper case.
    """
    return "{}.{}.{}".format(publisher_uid, package_uid, format_name).upper()


def check_fmf(package_metadata, format_metadata, fmf_path):
    """
    Checks the fmf file is consistent with the package and format metadata.

    :raises ValueError: If the fmf fails the check.
    :param package_metadata: The package metadata.
    :param format_metadata: The format metadata.
    :param fmf_path: The fmf file path.
    """
    with open(fmf_path) as inf:
        contents = inf.read()

    fqname = fq_format_short_name(
        package_metadata.publisher_uid, package_metadata.uid, format_metadata.name
    )

    if (
        "SOURCE_READER {}".format(fqname) not in contents
        or "FORMAT_NAME {}".format(fqname) not in contents
    ):
        raise ValueError("SOURCE_READER and FORMAT_NAME must be '{}'".format(fqname))


def check_formatinfo(package_metadata, format_metadata, db_path):
    """
    Checks formatinfo is consistent with the package and format metadata.

    :param package_metadata: The package metadata.
    :param format_metadata: The format metadata.
    :param db_path: The path to the format file.
    """
    line = None
    with open(db_path) as inf:
        for line in inf:
            if line.startswith(";"):
                continue  # comment line.

    if not line:
        raise ValueError("{} empty".format(db_path))

    fqname = fq_format_short_name(
        package_metadata.publisher_uid, package_metadata.uid, format_metadata.name
    )

    formatinfo = parse_formatinfo(line)
    if formatinfo.FORMAT_NAME != fqname:
        raise ValueError("{} must have FORMAT_NAME of '{}'".format(db_path, fqname))


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


class FMEPackager:
    def __init__(self, src_dir):
        self.src_dir = Path(src_dir)
        self.build_dir = self.src_dir / "build"
        self.dist_dir = self.src_dir / "dist"
        self.src_python_dir = self.src_dir / "python"

        self.metadata = load_fpkg_metadata(src_dir)

        validate(self.metadata.dict, load_metadata_json_schema())

    def apply_help(self, help_src):
        """
        Import an Safe TechPubs doc export into an FME Package directory.

        :param help_src: Help source path.
        """
        tmp_doc_dir = tempfile.mkdtemp(prefix="fme-packager_")
        try:
            # If help source is a ZIP, extract it to a temporary folder.
            if os.path.isfile(help_src):
                with zipfile.ZipFile(help_src) as zipf:
                    print("Extracting {} to {}".format(help_src, tmp_doc_dir))
                    zipf.extractall(tmp_doc_dir)
                root_contents = os.listdir(tmp_doc_dir)
                # If help ZIP started with a single root level folder, then unnest.
                if len(root_contents) == 1:
                    nested_dir = os.path.join(tmp_doc_dir, root_contents[0])
                    print("Flattening single top-level folder {}".format(nested_dir))
                    for item in os.listdir(nested_dir):
                        shutil.move(os.path.join(nested_dir, item), tmp_doc_dir)
                    os.rmdir(nested_dir)
                help_src = tmp_doc_dir

            # Parse flali file ahead of anything else.
            flali_path = os.path.join(help_src, "package_aliases.flali")
            with open(flali_path, encoding="utf-8") as xmlin:
                aliases_xml = xmltodict.parse(xmlin.read())

            embedded_doc_dirs = list(filter(lambda x: x.startswith("!"), os.listdir(help_src)))
            if embedded_doc_dirs:
                warnings.warn(
                    "{} embedded doc folders (starting with '!'). Avoid these if possible".format(
                        len(embedded_doc_dirs)
                    )
                )

            # (Re)create destination help folder and copy over the bulk of the doc files.
            dest = os.path.join(self.src_dir, "help")
            if os.path.exists(dest):
                print("Deleting {}".format(dest))
                shutil.rmtree(dest)
            shutil.copytree(help_src, dest, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))
        finally:
            shutil.rmtree(tmp_doc_dir)

        # Convert flali to CSV and put it in the destination.
        # Skip rows that refer to doc files that aren't present in the doc ZIP.
        copied_rows = 0
        with open(os.path.join(dest, "package_help.csv"), "w", newline="") as csvout:
            writer = csv.writer(csvout)
            rows = aliases_xml["CatapultAliasFile"]["Map"]
            if not isinstance(rows, list):
                rows = [rows]
            for row in rows:
                name = row["@Name"].replace(".", "_")
                link = row["@Link"]
                if link.startswith("/Content"):
                    new_link = link.replace("/Content", "", 1)
                    link = new_link
                expected_doc_path = os.path.join(dest, link.lstrip("/"))
                if os.path.exists(expected_doc_path):
                    print("{} exists".format(expected_doc_path))
                    writer.writerow([name, link])
                    copied_rows += 1
        print("Wrote {} of {} flali row(s) to package_help.csv".format(copied_rows, len(rows)))
        if not copied_rows:
            raise ValueError("flali doesn't reference any included doc")

    def make_fpkg(self):
        """
        Create an .fpkg file from package build files.
        """

        if not self.dist_dir.exists():
            self.dist_dir.mkdir(parents=True)

        fpkg_filename = build_fpkg_filename(
            self.metadata.publisher_uid, self.metadata.uid, self.metadata.version
        )
        fpkg_path = self.dist_dir / fpkg_filename
        print(f"Saving fpkg to {fpkg_path}")

        if fpkg_path.exists():
            fpkg_path.unlink()

        zipfile.main(["-c", str(fpkg_path), str(self.build_dir / ".")])
        print("Done.")

    def build(self):
        """
        Build and validate package files.
        """
        print("Collecting files into {}".format(self.build_dir))

        # Clear out the build dir.
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)

        for required_file in ["package.yml", "README.md", "CHANGES.md"]:
            check_exists_and_copy(self.src_dir / required_file, self.build_dir)

        self._copy_icon()

        self._copy_transformers()
        self._copy_web_services()
        self._copy_web_filesystems()
        self._copy_formats()
        self._copy_localization()
        self._copy_help()

        self._build_wheels()
        self._copy_wheels()
        self._check_wheels()

    def _copy_formats(self):
        # First, copy all files we don't specifically care about.
        # Ignore FMF and etc for formats not mentioned in metadata.
        src = self.src_dir / "formats"
        dst = self.build_dir / "formats"
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))

        for fmt in self.metadata.formats:
            print(f"Working on format: {fmt.name}")

            if not (dst / f"{fmt.name}.md").is_file():
                raise ValueError(f"{fmt.name} is missing doc")

            fms_path = src / f"{fmt.name}.fms"
            if fms_path.is_file():
                shutil.copy(fms_path, dst)

            fmf_path = src / f"{fmt.name}.fmf"
            if not fmf_path.is_file():
                raise ValueError(f"{fmf_path} is in metadata, but was not found")
            check_fmf(self.metadata, fmt, fmf_path)
            shutil.copy(fmf_path, dst)

            db_path = src / f"{fmt.name}.db"
            if not db_path.is_file():
                raise ValueError(f"{db_path} is in metadata, but was not found")
            check_formatinfo(self.metadata, fmt, db_path)
            shutil.copy(db_path, dst)

    def validate_transformer(self, transformer_path, expected_metadata: TransformerMetadata):
        print(f"Checking {transformer_path}")
        transformer_file = load_transformer(transformer_path)

        expected_fqname = "{}.{}.{}".format(
            self.metadata.publisher_uid, self.metadata.uid, expected_metadata.name
        )

        transformer_versions = list(transformer_file.versions())
        if not transformer_versions:
            raise ValueError(f"{transformer_path} defines no versions")
        # Validations below apply to all versions of the transformer
        for transformer in transformer_versions:
            if transformer.version < 1:
                raise ValueError(f"Invalid transformer version {transformer.version}")
            if transformer.name != expected_fqname:
                raise ValueError(f"Name must be '{expected_fqname}', not '{transformer.name}'")
            if isinstance(transformer, CustomTransformer):
                if transformer.header.insert_mode != '"Linked Always"':
                    raise ValueError(
                        f'Custom transformer Insert Mode must be "Linked Always", not {transformer.header.insert_mode}'
                    )
                if transformer.header.build_num < self.metadata.minimum_fme_build:
                    raise ValueError(
                        "Custom transformer created with FME build older than fme_minimum_build in package.yml"
                    )

        # Validations below apply only to the latest version of the transformer
        newest_transformer = transformer_versions[0]  # First definition in file
        if newest_transformer.version != expected_metadata.version:
            raise ValueError(f"Missing version {expected_metadata.version}")
        if not is_valid_python_compatibility(newest_transformer.python_compatibility):
            if not isinstance(newest_transformer, CustomTransformer):
                raise TransformerPythonCompatError(expected_metadata.name)
            elif (
                isinstance(newest_transformer, CustomTransformer)
                and newest_transformer.python_compatibility != "2or3"
            ):
                raise CustomTransformerPythonCompatError(expected_metadata.name)

    def _copy_transformers(self):
        # First, copy all files we don't specifically care about.
        # Ignore FMX and FMS for transformers not mentioned in metadata.
        src = self.src_dir / "transformers"
        dst = self.build_dir / "transformers"
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))

        for transformer in self.metadata.transformers:
            print(f"Working on transformer: {transformer.name}")

            if transformer.version < 1:
                raise ValueError(f"{transformer.name} version must be >= 1")

            if not (dst / f"{transformer.name}.md").is_file():
                raise ValueError(f"{transformer.name} is missing doc")

            fms_path = src / f"{transformer.name}.fms"
            if fms_path.is_file():
                shutil.copy(fms_path, dst)

            fmx_path = src / f"{transformer.name}.fmx"
            if not fmx_path.is_file():
                raise ValueError(f"{fmx_path} is in metadata, but was not found")

            # Copy file if it passed validation
            self.validate_transformer(fmx_path, transformer)
            shutil.copy(fmx_path, dst)

    def _copy_web_services(self):
        dest = self.build_dir / "web_services"
        for web_service in self.metadata.web_services:
            # fpkg spec says web service metadata entries must be full filename. Don't assume xml.
            definition_path = self.src_dir / "web_services" / web_service.name
            if not definition_path.exists():
                raise ValueError(
                    f"Web Service '{web_service.name}' is in metadata, but was not found"
                )
            if not dest.exists():
                dest.mkdir(parents=True)

            # TODO: Validate contents of XML.
            print(f"Copying Web Service: {definition_path.name}")
            shutil.copy(definition_path, dest)

    def _copy_web_filesystems(self):
        src = self.src_dir / "web_filesystems"
        dest = self.build_dir / "web_filesystems"
        for web_filesystem in self.metadata.web_filesystems:
            definition_path = src / f"{web_filesystem.name}.fme"
            if not definition_path.is_file():
                raise ValueError(
                    f"Web Filesystem '{web_filesystem.name}' is in metadata, but was not found"
                )
            if not dest.exists():
                dest.mkdir(parents=True)

            # TODO: Validate contents of .fme file.
            print(f"Copying Web Filesystem: {definition_path.name}")
            shutil.copy(definition_path, dest)

            icon_path = src / f"{web_filesystem.name}.png"
            if icon_path.is_file():
                enforce_png(icon_path)
                # Specification doesn't say anything about dimensions.
                shutil.copy(icon_path, dest)

    def _copy_icon(self):
        path = self.src_dir / "icon.png"
        if not path.is_file():
            print("FME package has no icon")
            return
        enforce_png(path, min_width=200, min_height=200, square=True)
        print("Icon is OK")
        shutil.copy(path, self.build_dir)

    def _build_wheels(self):
        original_cwd = os.getcwd()

        if not self.src_python_dir.exists():
            return

        for path in self.src_python_dir.iterdir():
            if (path / "setup.py").is_file() or (path / "setup.cfg").is_file():
                print(f"\nBuilding Python wheel: {path}")
                os.chdir(path)
                if os.path.exists("build"):
                    shutil.rmtree("build")
                # Simple solution to avoid needing to figure out which output is the one we want.
                # The only wheel in the directory will be the one to include in the fpkg.
                if os.path.exists("dist"):
                    shutil.rmtree("dist")
                try:
                    ProjectBuilder(".").build("wheel", "dist")
                finally:
                    os.chdir(original_cwd)

    def _copy_wheels(self):
        if not self.src_python_dir.is_dir():
            return

        wheels_dest = self.build_dir / "python"
        wheels_dest.mkdir(parents=True)

        for path in self.src_python_dir.iterdir():
            if os.path.isfile(path) and path.suffix == ".whl":
                shutil.copy(path, wheels_dest)

            built_wheels_dir = path / "dist"
            if built_wheels_dir.is_dir():
                built_wheels_for_lib = [
                    name for name in built_wheels_dir.iterdir() if name.suffix == ".whl"
                ]
                assert len(built_wheels_for_lib) == 1
                shutil.copy(built_wheels_dir / built_wheels_for_lib[0], wheels_dest)

    def _check_wheels(self):
        wheels_path = self.build_dir / "python"

        wheel_names = os.listdir(wheels_path) if wheels_path.is_dir() else []
        for expected_py_package in self.metadata.python_packages:
            lib_name = expected_py_package.name
            if not any(
                wheel_name.startswith(lib_name) or wheel_name.startswith(lib_name.replace("-", "_"))
                for wheel_name in wheel_names
            ):
                raise ValueError(
                    f"Python library '{lib_name}' is in metadata, but was not found"
                )

        if not wheels_path.is_dir():
            return
        for wheel_path in wheels_path.iterdir():
            wheel_name = wheel_path.name
            if "py3" not in wheel_name:
                warnings.warn("{} is not a Python 3 wheel".format(wheel_name))
            if not wheel_name.endswith("-none-any.whl"):
                warnings.warn("{} is not a pure-Python wheel".format(wheel_name))

    def _copy_localization(self):
        # Copy any optional localization files. The only sanity check is a filename whitelist:
        # guiprompts_??.txt, transformer-localized.??, FormatOrTransformerName_??.md
        # ?? is a 2-letter language code.
        # Contents of files aren't validated. It's up to Workbench to ignore anything malformed.
        dest = self.build_dir / "localization"
        src = self.src_dir / "localization"
        if not src.is_dir():
            return

        keywords = [f.name for f in self.metadata.formats] + [
            t.name for t in self.metadata.transformers
        ]
        localized_doc_globs = [keyword + "_??.md" for keyword in keywords]

        for name in os.listdir(src):
            path = src / name
            if (
                fnmatch(name, "guiprompts_??.txt")
                or fnmatch(name, "transformer-localized.??")
                or any(fnmatch(name, glob) for glob in localized_doc_globs)
            ):
                if not os.path.exists(dest):
                    os.makedirs(dest)
                print(f"Copying localization: {name}")
                shutil.copy(path, dest)

    def _copy_help(self):
        src = self.src_dir / "help"
        dest = self.build_dir / "help"
        if not src.is_dir():
            return

        print("Copying help")
        # Validate help index...
        with open(src / "package_help.csv", newline="") as csvin:
            for row in csv.reader(csvin):
                if "." in row[0]:
                    raise ValueError(f"{row[0]} cannot contain '.'")
                expected_doc = src / row[1].lstrip("/")
                if not expected_doc.exists():
                    raise ValueError(f"Help entry {expected_doc} does not exist")

        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))
