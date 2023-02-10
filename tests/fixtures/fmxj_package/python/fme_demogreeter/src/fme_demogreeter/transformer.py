"""
example.my-package.DemoGreeter implementation.
"""
from fmeobjects import FMEFeature
from ._vendor.fmetools.plugins import FMEEnhancedTransformer
from ._vendor.fmetools.guiparams import GuiParameterParser


# Build a parser for getting GUI parameter values from input features.
# It takes a mapping of the internal attribute name to the GUI type supplying its value.
param_parser = GuiParameterParser(
    {
        "___XF_FIRST_NAME": "STRING_OR_ATTR_ENCODED",
    }
)


class TransformerImpl(FMEEnhancedTransformer):
    """
    The Python implementation of the DemoGreeter transformer.
    Each instance of the transformer in the workspace has an instance of this class.
    """

    def __init__(self):
        super(TransformerImpl, self).__init__()

    def receive_feature(self, feature: FMEFeature):
        """
        Receive an input feature.
        """
        # Use the GUI parameter parser to get parameter from the input feature.
        first_name = param_parser.get(feature, "___XF_FIRST_NAME")

        # Set the output attribute, and output the feature.
        feature.setAttribute("_greeting", "Hello, {}!".format(first_name))
        self.pyoutput(feature)

    def process_group(self):
        # TODO: Implement as described in overriden method's docstring
        # Group-Based Transformers accumulate features in receive_feature().
        # When FME calls this method, process the accumulated features, output results,
        # and clear the accumulated features in preparation for the next group, if any.
        pass
