class TransformerPythonCompatError(ValueError):
    """Exception raised when PYTHON_COMPATIBILITY is set to unsupported version for Transformers."""

    def __init__(self, transformer_name):
        message = "'{}' Python compatibility must be >=36.".format(transformer_name)
        super().__init__(message)


class CustomTransformerPythonCompatError(ValueError):
    """Exception raised when PYTHON_COMPATIBILITY is set to unsupported version for Custom Transformers."""

    def __init__(self, transformer_name):
        message = "'{}' Python compatibility must be '2or3' or >=36.".format(transformer_name)
        super().__init__(message)
