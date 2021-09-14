import csv
import imghdr
import os
import re
import shutil
import tempfile
import warnings
import zipfile
from fnmatch import fnmatch

import png
import xmltodict
from jsonschema import validate
from distutils.core import run_setup

from fpkgr.metadata import load_fpkg_metadata, load_metadata_json_schema
from fpkgr.operations import build_fpkg_filename, parse_formatinfo, get_custom_transformer_header


def check_exists_and_copy(src, dest):
    if not os.path.exists(src):
        raise ValueError("{} is required but does not exist".format(src))
    shutil.copy(src, dest)


def enforce_png(path, min_width=0, min_height=0, square=False):
    filetype = imghdr.what(path)
    if filetype != 'png':
        raise ValueError("{} must be PNG, not {}".format(path, filetype))
    width, height, _, _ = png.Reader(filename=path).read()
    if width < min_width or height < min_height:
        raise ValueError("Min dimensions are {}x{}. {} is {}x{}".format(min_width, min_height, path, width, height))
    if square and width != height:
        raise ValueError("{} must be square".format(path))


def check_fmx(package_metadata, transformer_metadata, fmx_path):
    with open(fmx_path) as inf:
        contents = inf.read()

    if 'TRANSFORMER_NAME:' not in contents or 'VERSION:' not in contents:
        raise ValueError('{} missing TRANSFORMER_NAME or VERSION'.format(fmx_path))

    fqname = '{}.{}.{}'.format(package_metadata.publisher_uid, package_metadata.uid, transformer_metadata.name)
    transformer_names = list(re.finditer(r'\nTRANSFORMER_NAME:\s*([^\n]+)\n'.format(fqname), contents))
    if not transformer_names:
        raise ValueError("{} missing TRANSFORMER_NAME".format(fmx_path))
    for match in transformer_names:
        name = match.group(1)
        if name != fqname:
            raise ValueError("{} all TRANSFORMER_NAME need to be '{}', not '{}'".format(fmx_path, fqname, name))

    if not re.findall(r'\nVERSION:\s*{}\n'.format(transformer_metadata.version), contents):
        raise ValueError("{} is missing VERSION {}".format(fmx_path, transformer_metadata.version))

    _validate_fmx_fme_python_version(contents, fmx_path)


def _validate_fmx_fme_python_version(contents, fmx_path):
    invalid_versions = {"27", "ArcGISDesktop"}

    fme_python_version = re.finditer(r'\nPYTHON_COMPATIBILITY:\s*([^\n]+)\n', contents)
    for match in fme_python_version:
        python_version = match.group(1)
        if python_version in invalid_versions:
            raise ValueError(
                "{} specifies PYTHON_COMPATIBILITY: '{}' which is not supported to be packaged.".format(fmx_path, python_version))


def check_custom_fmx(package_metadata, transformer_metadata, fmx_path):
    # Cheating here. Only looking at the topmost (first and latest) TRANSFORMER_BEGIN.
    header = get_custom_transformer_header(fmx_path)

    fqname = '{}.{}.{}'.format(package_metadata.publisher_uid, package_metadata.uid, transformer_metadata.name)
    if header.name != fqname:
        raise ValueError("{} name needs to be '{}', not '{}'".format(fmx_path, fqname, header.name))

    if transformer_metadata.version != header.version:
        raise ValueError("{} is missing version {}".format(fmx_path, transformer_metadata.version))

    if header.insert_mode != '"Linked Always"':
        raise ValueError('Custom transformer Insert Mode must be "Linked Always", not {}'.format(header.insert_mode))

    build_num = int(header.build_num)
    if build_num < 19000:
        raise ValueError('Custom transformer must be created from FME build 19000 or newer')
    if build_num < package_metadata.minimum_fme_build:
        raise ValueError('Custom transformer created with FME build older than fme_minimum_build in package.yml')

    if header.pyver != '2or3' and not header.pyver.startswith('3'):
        raise ValueError('Custom transformer Python Compatibility must be "2or3" or 3x')


def fq_format_short_name(publisher_uid, package_uid, format_name):
    return '{}.{}.{}'.format(publisher_uid, package_uid, format_name).upper()


def check_fmf(package_metadata, format_metadata, fmf_path):
    with open(fmf_path) as inf:
        contents = inf.read()

    fqname = fq_format_short_name(package_metadata.publisher_uid, package_metadata.uid, format_metadata.name)

    if 'SOURCE_READER {}'.format(fqname) not in contents or 'FORMAT_NAME {}'.format(fqname) not in contents:
        raise ValueError("SOURCE_READER and FORMAT_NAME must be '{}'".format(fqname))


def check_formatinfo(package_metadata, format_metadata, db_path):
    line = None
    with open(db_path) as inf:
        for line in inf:
            if line.startswith(';'):
                continue  # comment line.

    if not line:
        raise ValueError('{} empty'.format(db_path))

    fqname = fq_format_short_name(package_metadata.publisher_uid, package_metadata.uid, format_metadata.name)

    formatinfo = parse_formatinfo(line)
    if formatinfo.FORMAT_NAME != fqname:
        raise ValueError("{} must have FORMAT_NAME of '{}'".format(db_path, fqname))


# Matches files that should not automatically be copied into an fpkg.
# Some of these are OS-specific metadata.
# FME file extensions are here because their copy over is gated by validation.
TREE_COPY_IGNORE_GLOBS = [
    '.*', '*.mclog', '*.flali',
    '*.fmf', '*.fmx', '*.db', '*.fms',
    '.DS_Store', 'Thumbs.db', 'desktop.ini',
]


class FMEPackager:
    def __init__(self, src_dir):
        self.src_dir = src_dir
        self.build_dir = os.path.join(src_dir, 'build')
        self.dist_dir = os.path.join(src_dir, 'dist')
        self.src_python_dir = os.path.join(src_dir, 'python')

        self.metadata = load_fpkg_metadata(src_dir)

        validate(self.metadata.dict, load_metadata_json_schema())

    def build(self):
        print('Collecting files into {}'.format(self.build_dir))

        # Clear out the build dir.
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir)
        os.makedirs(self.build_dir)

        for required_file in ['package.yml', 'README.md', 'CHANGES.md']:
            check_exists_and_copy(os.path.join(self.src_dir, required_file), self.build_dir)

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
        src = os.path.join(self.src_dir, 'formats')
        dst = os.path.join(self.build_dir, 'formats')
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))

        for format in self.metadata.formats:
            print('Working on format: {}'.format(format.name))

            if not os.path.isfile(os.path.join(dst, '{}.md'.format(format.name))):
                raise ValueError("{} is missing doc".format(format.name))

            fms_path = os.path.join(src, "{}.fms".format(format.name))
            if os.path.isfile(fms_path):
                shutil.copy(fms_path, dst)

            fmf_path = os.path.join(src, "{}.fmf".format(format.name))
            if not os.path.exists(fmf_path):
                raise ValueError("{} is in metadata, but was not found".format(fmf_path))
            check_fmf(self.metadata, format, fmf_path)
            shutil.copy(fmf_path, dst)

            db_path = os.path.join(src, "{}.db".format(format.name))
            if not os.path.exists(db_path):
                raise ValueError("{} is in metadata, but was not found".format(db_path))
            check_formatinfo(self.metadata, format, db_path)
            shutil.copy(db_path, dst)

    def _copy_transformers(self):
        # First, copy all files we don't specifically care about.
        # Ignore FMX and FMS for transformers not mentioned in metadata.
        src = os.path.join(self.src_dir, 'transformers')
        dst = os.path.join(self.build_dir, 'transformers')
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))

        for transformer in self.metadata.transformers:
            print('Working on transformer: {}'.format(transformer.name))

            if transformer.version < 1:
                raise ValueError('{} version must be >= 1'.format(transformer.name))

            if not os.path.isfile(os.path.join(dst, '{}.md'.format(transformer.name))):
                raise ValueError("{} is missing doc".format(transformer.name))

            fms_path = os.path.join(src, "{}.fms".format(transformer.name))
            if os.path.isfile(fms_path):
                shutil.copy(fms_path, dst)

            fmx_path = os.path.join(src, "{}.fmx".format(transformer.name))
            if not os.path.isfile(fmx_path):
                raise ValueError("{} is in metadata, but was not found".format(fmx_path))

            if get_custom_transformer_header(fmx_path):
                print('{} is a custom transformer'.format(transformer.name))
                check_custom_fmx(self.metadata, transformer, fmx_path)
            else:
                print('{} is not a custom transformer'.format(transformer.name))
                check_fmx(self.metadata, transformer, fmx_path)
            shutil.copy(fmx_path, dst)

    def _copy_web_services(self):
        dest = os.path.join(self.build_dir, 'web_services')
        for web_service in self.metadata.web_services:
            # fpkg spec says web service metadata entries must be full filename. Don't assume xml.
            definition_path = os.path.join(self.src_dir, 'web_services', web_service.name)
            if not os.path.exists(definition_path):
                raise ValueError("Web Service '{}' is in metadata, but was not found".format(web_service.name))
            if not os.path.exists(dest):
                os.makedirs(dest)

            # TODO: Validate contents of XML.
            shutil.copy(definition_path, dest)

    def _copy_web_filesystems(self):
        src = os.path.join(self.src_dir, 'web_filesystems')
        dest = os.path.join(self.build_dir, 'web_filesystems')
        for web_filesystem in self.metadata.web_filesystems:
            definition_path = os.path.join(src, '{}.fme'.format(web_filesystem.name))
            if not os.path.exists(definition_path):
                raise ValueError("Web Filesystem '{}' is in metadata, but was not found".format(web_filesystem.name))
            if not os.path.exists(dest):
                os.makedirs(dest)

            # TODO: Validate contents of .fme file.
            shutil.copy(definition_path, dest)

            icon_path = os.path.join(src, '{}.png'.format(web_filesystem.name))
            if os.path.exists(icon_path):
                enforce_png(icon_path)
                # Specification doesn't say anything about dimensions.
                shutil.copy(icon_path, dest)

    def _copy_icon(self):
        path = os.path.join(self.src_dir, 'icon.png')
        if not os.path.exists(path):
            print('FME package has no icon')
            return
        enforce_png(path, min_width=200, min_height=200, square=True)
        print("Icon is OK")
        shutil.copy(path, self.build_dir)

    def _build_wheels(self):
        original_cwd = os.getcwd()

        if not os.path.exists(self.src_python_dir):
            return

        for name in os.listdir(self.src_python_dir):
            path = os.path.join(self.src_python_dir, name)
            if os.path.isdir(path) and os.path.isfile(os.path.join(path, 'setup.py')):
                print("\nBuilding Python wheel: {}".format(path))
                os.chdir(path)
                if os.path.exists('build'):
                    shutil.rmtree('build')
                # Simple solution to avoid needing to figure out which built artifact is the one we want.
                # The only wheel in the directory will be the one to include in the fpkg.
                if os.path.exists('dist'):
                    shutil.rmtree('dist')
                try:
                    run_setup('setup.py', ['bdist_wheel'])
                finally:
                    os.chdir(original_cwd)

    def _copy_wheels(self):
        if not os.path.exists(self.src_python_dir):
            return

        wheels_dest = os.path.join(self.build_dir, 'python')
        os.mkdir(wheels_dest)

        for name in os.listdir(self.src_python_dir):
            path = os.path.join(self.src_python_dir, name)
            if os.path.isfile(path) and path.endswith('.whl'):
                shutil.copy(path, wheels_dest)

            built_wheels_dir = os.path.join(path, 'dist')
            if os.path.isfile(os.path.join(path, 'setup.py')) and os.path.isdir(built_wheels_dir):
                built_wheels_for_lib = [name for name in os.listdir(built_wheels_dir) if name.endswith('.whl')]
                assert len(built_wheels_for_lib) == 1
                shutil.copy(os.path.join(built_wheels_dir, built_wheels_for_lib[0]), wheels_dest)

    def _check_wheels(self):
        wheels = os.listdir(os.path.join(self.build_dir, 'python'))
        for wheel_name in wheels:
            if 'py2.py3' not in wheel_name:
                warnings.warn('{} is not a Python universal wheel'.format(wheel_name))
            if not wheel_name.endswith('-none-any.whl'):
                warnings.warn('{} is not a pure-Python wheel'.format(wheel_name))

        for expected_py_package in self.metadata.python_packages:
            lib_name = expected_py_package.name
            if not any(
                wheel_name.startswith(lib_name) or wheel_name.startswith(lib_name.replace('-', '_')) for wheel_name in
                wheels):
                raise ValueError("Python library '{}' is in metadata, but was not found".format(lib_name))

    def _copy_localization(self):
        # Copy any optional localization files. The only sanity check is a filename whitelist:
        # guiprompts_??.txt, transformer-localized.??, FormatOrTransformerName_??.md
        # ?? is a 2-letter language code.
        # Contents of files aren't validated. It's up to Workbench to ignore anything malformed.
        dest = os.path.join(self.build_dir, 'localization')
        src = os.path.join(self.src_dir, 'localization')
        if not os.path.isdir(src):
            return

        keywords = [f.name for f in self.metadata.formats] + [t.name for t in self.metadata.transformers]
        localized_doc_globs = [keyword + '_??.md' for keyword in keywords]

        for name in os.listdir(src):
            path = os.path.join(src, name)
            if fnmatch(name, 'guiprompts_??.txt') or fnmatch(name, 'transformer-localized.??') or \
                any(fnmatch(name, glob) for glob in localized_doc_globs):
                if not os.path.exists(dest):
                    os.makedirs(dest)
                print('Copying localization: ' + name)
                shutil.copy(path, dest)

    def apply_help(self, help_src):
        tmp_doc_dir = tempfile.mkdtemp(prefix="fpkgr_")
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
                        len(embedded_doc_dirs)))

            # (Re)create destination help folder and copy over the bulk of the doc files.
            dest = os.path.join(self.src_dir, "help")
            if os.path.exists(dest):
                print("Deleting {}".format(dest))
                shutil.rmtree(dest)
            shutil.copytree(
                help_src, dest,
                ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))
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

    def _copy_help(self):
        src = os.path.join(self.src_dir, "help")
        dest = os.path.join(self.build_dir, "help")
        if not os.path.isdir(src):
            return

        print("Copying help")
        # Validate help index...
        with open(os.path.join(src, "package_help.csv"), newline="") as csvin:
            for row in csv.reader(csvin):
                if "." in row[0]:
                    raise ValueError("{} cannot contain '.'".format(row[0]))
                expected_doc = os.path.join(src, row[1].lstrip("/"))
                if not os.path.exists(expected_doc):
                    raise ValueError("Help entry {} does not exist".format(expected_doc))

        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS))

    def make_fpkg(self):
        if not os.path.exists(self.dist_dir):
            os.makedirs(self.dist_dir)

        fpkg_filename = build_fpkg_filename(self.metadata.publisher_uid, self.metadata.uid, self.metadata.version)
        fpkg_path = os.path.join(self.dist_dir, fpkg_filename)
        print('Saving fpkg to {}'.format(fpkg_path))

        if os.path.exists(fpkg_path):
            os.remove(fpkg_path)

        zipfile.main(['-c', fpkg_path, os.path.join(self.build_dir, '.')])
        print('Done.')
