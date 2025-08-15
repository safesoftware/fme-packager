import tempfile
from json import dumps as json_dumps
from pathlib import Path

from fme_packager.operations import extract_fpkg
from fme_packager.packager import FMEPackager


class FMEVerifier:
    def __init__(self, file, verbose=False, output_json=False):
        self.file = Path(file)
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
        if not self.file.is_file() or not self.file.suffix.lower() == ".fpkg":
            raise ValueError("The file must exist and have a .fpkg extension")

        with tempfile.TemporaryDirectory() as temp_dir:
            extract_fpkg(self.file, temp_dir)

            # Verify the fpkg files by building the package
            steps = FMEPackager(temp_dir, self.verbose)
            steps.build()
            steps.make_fpkg()

    def _print(self, msg):
        if self.verbose:
            print(msg)
