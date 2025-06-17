"""
Tools for extracting key information out of FME's transformer definition files.
"""

import json
import os.path
import re
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Optional


class Transformer(ABC):
    """Represents one version of a transformer."""

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def version(self):
        pass

    @property
    @abstractmethod
    def python_compatibility(self):
        pass

    @property
    @abstractmethod
    def categories(self):
        pass

    @property
    @abstractmethod
    def aliases(self):
        pass

    @property
    @abstractmethod
    def visible(self):
        pass

    @property
    @abstractmethod
    def data_processing_types(self):
        pass


NamedTransformerHeader = namedtuple(
    "NamedTransformerHeader",
    "name version category guid insert_mode blocked_looping process_count process_group_by process_groups_ordered build_num preserves_attrs deprecated pyver preserve_group_attr replaced_by data_processing_type",
)


def parse_custom_transformer_header(line):
    """
    Parses custom transformer header.

    :param str line: Custom transformer header line from FMX.
    :return: Parsed header
    """
    fields = line.replace("# TRANSFORMER_BEGIN", "").strip().split(",")

    num_fields_expected = len(NamedTransformerHeader._fields)
    while len(fields) < num_fields_expected:
        fields.append("")

    header = NamedTransformerHeader(*fields[:num_fields_expected])
    data_processing_type = [] if not header.data_processing_type else [header.data_processing_type]

    return header._replace(
        version=int(header.version),
        build_num=int(header.build_num),
        data_processing_type=data_processing_type,
    )


class CustomTransformer(Transformer):
    def __init__(self, lines):
        super().__init__()
        self.header: NamedTransformerHeader
        self.lines = lines
        for line in lines:
            if line.startswith(b"# TRANSFORMER_BEGIN"):
                self.header = parse_custom_transformer_header(line.decode("utf8"))
                break
        else:
            raise ValueError("TRANSFORMER_BEGIN line not found")

    @property
    def name(self):
        return self.header.name

    @property
    def version(self):
        return self.header.version

    @property
    def python_compatibility(self):
        return self.header.pyver

    @property
    def categories(self):
        return self._split_prop("category", ",")

    @property
    def aliases(self):
        return []

    @property
    def visible(self):
        return self.header.deprecated.lower() == "no"

    @property
    def data_processing_types(self):
        return self.header.data_processing_type

    @property
    def is_encrypted(self):
        return self.lines[0].strip() == b"FMW0001"

    def _split_prop(self, property_name, sep=","):
        return (
            [p.strip() for p in getattr(self.header, property_name).split(sep)]
            if getattr(self.header, property_name)
            else []
        )


class FmxTransformer(Transformer):
    def __init__(self, lines):
        super().__init__()
        self.lines = lines
        self.props = {}
        for line in self.lines:
            match = re.match(r"^(.+?):\s+(.+?)$", line)
            if match:
                name = match.group(1).strip()
                if name.startswith("PARAMETER_"):
                    continue
                self.props[name] = match.group(2).strip()
        if self.name is None or self.version is None:
            raise ValueError("TRANSFORMER_NAME or VERSION not found")

    @property
    def name(self):
        return self.props.get("TRANSFORMER_NAME")

    @property
    def version(self):
        return int(self.props.get("VERSION"))

    @property
    def python_compatibility(self):
        return self.props.get("PYTHON_COMPATIBILITY")

    def _split_prop(self, property_name, sep=","):
        return (
            [p.strip() for p in self.props.get(property_name).split(sep)]
            if self.props.get(property_name)
            else []
        )

    @property
    def categories(self):
        return self._split_prop("CATEGORY", ",")

    @property
    def aliases(self):
        return self._split_prop("ALIASES", " ")

    @property
    def visible(self):
        return self.props.get("VISIBLE", "yes").lower() == "yes"

    @property
    def data_processing_types(self):
        data_processing_type = self.props.get("DATA_PROCESSING_TYPE")
        if not data_processing_type:
            return []
        
        data_processing_type = data_processing_type.strip()
        
        try:
            data_processing_type = json.loads(data_processing_type)
            
            if isinstance(data_processing_type, dict):
                types = set()
                
                if_conditions = data_processing_type.get("if", [])
                for condition in if_conditions:
                    then_value = condition.get("then")
                    if then_value:
                        types.add(then_value)
                
                default_value = data_processing_type.get("default")
                if default_value:
                    types.add(default_value)
                
                return sorted(list(types))
            
            elif isinstance(data_processing_type, str):
                return [data_processing_type]
                
        except json.JSONDecodeError:
            pass
        
        # Handle simple string case
        return [data_processing_type]


class FmxjTransformer(Transformer):
    def __init__(self, info, version_def):
        self.info = info
        self.json_def = version_def

    @property
    def name(self):
        return self.info["name"]

    @property
    def version(self):
        return self.json_def["version"]

    @property
    def python_compatibility(self):
        # FIXME: key typo from tstportConfiguration/testdata/PortConfiguration.fmxj
        return self.json_def.get("pythonCompatability")

    @property
    def categories(self):
        return self.info.get("categories", [])

    @property
    def aliases(self):
        return self.info.get("aliases", [])

    @property
    def visible(self):
        return not self.info.get("deprecated", False)

    @property
    def data_processing_types(self):
        data_processing_type = self.json_def.get("dataProcessingType")
        if not data_processing_type:
            return []
        
        # Handle simple string case
        if isinstance(data_processing_type, str):
            return [data_processing_type]
        
        # Handle conditional logic case
        if isinstance(data_processing_type, dict):
            types = set()
            
            # Extract all "then" values from conditional statements
            if_conditions = data_processing_type.get("if", [])
            for condition in if_conditions:
                then_value = condition.get("then")
                if then_value:
                    types.add(then_value)
            
            # Add default value if present
            default_value = data_processing_type.get("default")
            if default_value:
                types.add(default_value)
            
            return sorted(list(types))
        
        return []


class TransformerFile(ABC):
    """Represents a transformer file containing one or more transformer versions."""

    def __init__(self, file_path):
        self.file_path = file_path

    @abstractmethod
    def versions(self):
        pass


def get_matching_indexes(lines, matcher):
    """
    Returns indexes of lines where line is (or can be decoded as) UTF-8 and matcher function is true.
    """
    indexes = []
    for i, line in enumerate(lines):
        if not isinstance(line, str):
            try:
                line = line.decode("utf8")
            except (UnicodeDecodeError, AttributeError):
                continue
        if matcher(line):
            indexes.append(i)
    return indexes


class FmxFile(TransformerFile):
    def __init__(self, file_path):
        super().__init__(file_path)

    def versions(self):
        with open(self.file_path, "r") as f:
            lines = f.readlines()
        transformer_begin_indexes = get_matching_indexes(
            lines, lambda l: l.startswith("TRANSFORMER_NAME")
        )
        for def_num, i in enumerate(transformer_begin_indexes):
            if i == transformer_begin_indexes[-1]:
                end_idx = len(lines) - 1
            else:
                end_idx = transformer_begin_indexes[def_num + 1] - 1
            yield FmxTransformer(lines[i:end_idx])


class CustomTransformerFmxFile(TransformerFile):
    def __init__(self, file_path):
        super().__init__(file_path)

    def versions(self):
        with open(self.file_path, "rb") as f:
            lines = f.readlines()
        transformer_begin_indexes = get_matching_indexes(
            lines, lambda l: l.startswith("# TRANSFORMER_BEGIN")
        )
        for def_num, i in enumerate(transformer_begin_indexes):
            if i == transformer_begin_indexes[-1]:
                end_idx = len(lines) - 1
            else:
                end_idx = transformer_begin_indexes[def_num + 1] - 2
            yield CustomTransformer(lines[i - 1 : end_idx])


class FmxjFile(TransformerFile):
    def __init__(self, file_path):
        super().__init__(file_path)
        with open(file_path) as f:
            self.body = json.load(f)

    def versions(self):
        for item in self.body["versions"]:
            yield FmxjTransformer(self.body["info"], item)


def load_transformer(transformer_path) -> TransformerFile:
    filename, ext = os.path.splitext(transformer_path)
    ext = ext.lower()
    if ext == ".fmx":
        # Check first line for Custom Transformer text
        with open(transformer_path, "rb") as f:
            line = f.readline()
        if line.startswith(b"#!") or line.startswith(b"FMW0001"):
            return CustomTransformerFmxFile(transformer_path)
        return FmxFile(transformer_path)
    if ext == ".fmxj":
        return FmxjFile(transformer_path)
    raise ValueError(f"Unrecognized transformer: {transformer_path}")
