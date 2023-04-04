import shutil
import tempfile
import os

from fme_packager.packager import FMEPackager


class FMEVerifier:
    def __init__(self, file):
        self.file = file
        pass

    def verify(self):
        if not self.file.name.lower().endswith(".fpkg"):
            raise ValueError("The file must have a .fpkg extension")

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change the extension of the file to .zip
            temp_zip_file_path = self.file.name[:-5] + ".zip"
            shutil.copy(self.file.name, temp_zip_file_path)

            # Unpack the zip file
            shutil.unpack_archive(temp_zip_file_path, temp_dir)

            # Verify the fpkg files by building the package
            steps = FMEPackager(temp_dir)
            try:
                steps.build()
            finally:
                # Remove the temporary zip file path created earlier
                os.remove(temp_zip_file_path)
