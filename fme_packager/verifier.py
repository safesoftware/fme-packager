import shutil
import tempfile
from json import dumps as json_dumps

from fme_packager.extractor import _zip_filename_for_fpkg
from fme_packager.operations import valid_fpkg_file
from fme_packager.packager import FMEPackager


class FMEVerifier:
    def __init__(self, file, verbose=False, output_json=False):
        self.file = file
        self.verbose = verbose
        self.output_json = output_json

    def verify(self):
        success, message = True, "valid"
        try:
            self._unzip_and_build()
        except Exception as e:
            success, message = False, str(e)

        if self.output_json:
            result = json_dumps({"status": "success" if success else "error", "message": message})
        else:
            result = "Success: Package Valid" if success else f"Error Validating Package: {message}"

        return result

    def _unzip_and_build(self):
        self.file = valid_fpkg_file(self.file)

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change the extension of the file to .zip
            temp_zip_file = str(_zip_filename_for_fpkg(temp_dir, self.file))
            self._print(f"Creating temporary zip file {temp_zip_file}")
            shutil.copy(self.file, temp_zip_file)

            # Unpack the zip file
            shutil.unpack_archive(temp_zip_file, temp_dir)

            # Verify the fpkg files by building the package
            steps = FMEPackager(temp_dir, self.verbose)
            steps.build()
            steps.make_fpkg()

    def _print(self, msg):
        if self.verbose:
            print(msg)
