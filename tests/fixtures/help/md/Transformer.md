# Transformer
A description of the transformer.

## Typical uses
Displays "Hello, `FIRST_NAME`!"

## How does it work?
Description of how the transformer works.

## Configuration
### Input Ports
#### Input
This transformer accepts any feature.
### Output Ports
#### Output
- **_greeting:** Output greeting with the specified name.

#### <Rejected>
Features that cause the operation to fail are output through this port.
Rejected features have `fme_rejection_code` and `fme_rejection_message` attributes
which specify the reason for the failure.

**Note:** If the input feature has an existing value for `fme_rejection_code`, the value will be removed.

**Rejected Feature Handling:** Ban be set to either terminate the translation or
continue running when it encounters a rejected feature.
This setting is available both as a default [FME option](https://docs.safe.com/fme/html/FME_Desktop_Documentation/FME_Workbench/Workbench/options_workspace_defaults.htm)
and as a [workspace parameter](https://docs.safe.com/fme/html/FME_Desktop_Documentation/FME_Workbench/Workbench/workspace_parameters.htm).

### Parameters
#### Options
- **First Name:** First name to be greeted by. Defaults to "World".
