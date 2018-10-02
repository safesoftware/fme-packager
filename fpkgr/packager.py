import imghdr
import os
import re
import shutil
import warnings
import zipfile

import png
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


def check_fmf(package_metadata, format_metadata, fmf_path):
    with open(fmf_path) as inf:
        contents = inf.read()

    fqname = '{}.{}.{}'.format(package_metadata.publisher_uid, package_metadata.uid, format_metadata.name.upper())

    if 'SOURCE_READER {}'.format(fqname) not in contents or 'FORMAT_NAME {}'.format(fqname) not in contents:
        raise ValueError("SOURCE_READER and FORMAT_NAME must be '{}'".format(fqname))


def check_formatinfo(package_metadata, format_metadata, db_path):
    with open(db_path) as inf:
        contents = inf.read()

    fqname = '{}.{}.{}'.format(package_metadata.publisher_uid, package_metadata.uid, format_metadata.name.upper())

    formatinfo = parse_formatinfo(contents)
    if formatinfo.FORMAT_NAME != fqname:
        raise ValueError("{} must have FORMAT_NAME of '{}'".format(db_path, fqname))


class FMEPackager:
    def __init__(self, src_dir):
        self.src_dir = src_dir
        self.build_dir = os.path.join(src_dir, 'build')
        self.dist_dir = os.path.join(src_dir, 'dist')
        self.src_python_dir = os.path.join(src_dir, 'python')

        self.metadata = load_fpkg_metadata(src_dir)

        validate(self.metadata.dict, load_metadata_json_schema())

        print('Collecting files into {}'.format(self.build_dir))

        # Clear out the build dir.
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir)
        os.makedirs(self.build_dir)

        for required_file in ['package.yml', 'README.md', 'CHANGES.md']:
            check_exists_and_copy(os.path.join(self.src_dir, required_file), self.build_dir)

    def build(self):
        self._copy_icon()

        self._copy_transformers()
        self._copy_web_services()
        self._copy_web_filesystems()

        self._build_wheels()
        self._copy_wheels()
        self._check_wheels()

    def _copy_formats(self):
        # First, copy all files we don't specifically care about.
        # Ignore FMF and etc for formats not mentioned in metadata.
        src = os.path.join(self.src_dir, 'transformers')
        dst = os.path.join(self.build_dir, 'transformers')
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('*.fmf', '*.db', '*.fms'))

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

            db_path = os.path.join(src, "{}.db".format(format.db))
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
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('*.fmx', '*.fms'))

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
                os.chdir(path)
                if os.path.exists('build'):
                    shutil.rmtree('build')
                try:
                    run_setup('setup.py', ['bdist_wheel'])
                finally:
                    os.chdir(original_cwd)

    def _copy_wheels(self):
        wheels_dest = os.path.join(self.build_dir, 'python')
        os.mkdir(wheels_dest)

        if not os.path.exists(self.src_python_dir):
            return

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
            if not any(wheel_name.startswith(lib_name) for wheel_name in wheels):
                raise ValueError("Python library '{}' is in metadata, but was not found".format(lib_name))

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
