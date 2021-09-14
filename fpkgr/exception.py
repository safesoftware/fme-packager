class PythonCompatibilityError(ValueError):
    """Exception raised when PYTHON_COMPATIBILITY is set to unsupported version."""
    def __init__(self):
        super().__init__("Custom transformer Python Compatibility must be >=36.")
