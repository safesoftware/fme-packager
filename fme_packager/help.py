"""
Logic for preparing help documentation for the FPKG packing process.

- package_help.csv validation
- File copy logic for the help folder
- Markdown to HTML conversion and package_help.csv generation
"""
import csv
import re
import shutil
import warnings
from pathlib import Path

from markdown import Markdown

from fme_packager.metadata import FMEPackageMetadata
from fme_packager.operations import TREE_COPY_IGNORE_GLOBS


HTML_TPL = """<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
<link rel="stylesheet" href="{css_path}" />
</head>
<body>
{body}
</body>
</html>
"""


def add_transformer_classes_to_doc(html):
    """
    Given a string that is HTML doc, modify the first h1 and p tags
    to mark the relevant contents to show for the FME Workbench Quick Add pane.
    See FMEENGINE-75813.

    Assumes that:
    - these tags don't already have a class attribute
    - the HTML was generated by python-markdown without extensions that modify tags
    """
    # Must be exact match: Workbench finds these tags through text search, not DOM.
    html, _ = re.subn(r"<h1>", '<h1 class="fmx">', html, count=1)
    html, _ = re.subn(r"<p>", '<p><span class="TransformerSummary">', html, count=1)
    html, _ = re.subn(r"</p>", "</span></p>", html, count=1)
    return html


class DocCopier:
    """
    Callable with the same signature as shutil.copy2(), for use with shutil.copytree().
    Copies files while converting MD files to HTML at the destination.
    Identical to shutil.copy2() when conversion is disabled.
    """

    def __init__(self, root_path):
        """
        :param root_path: All files copied must be descendants of this root.
            Used to determine hardcoded relative paths in generated HTML.
        """
        self.root_path = root_path
        self.convert_md = True
        self.converted_files = {}
        self._md_converter = Markdown(
            extensions=[
                "tables",
                "fenced_code",
            ],
        )
        # DEVOPS-3078: Path to CSS relative to the doc root folder
        self._css_path_rel_doc = "../../css/style.css"

        # When generating HTML, transformer doc gets special treatment.
        self.transformer_names = set()

    def md_to_html(self, src_file: Path):
        # Not using python-markdown extensions API because this is a one-off task.
        body = self._md_converter.reset().convert(src_file.read_text("utf8"))
        if src_file.stem in self.transformer_names:
            body = add_transformer_classes_to_doc(body)
        # Count number of subfolders down from the root,
        # so the CSS relative path gets updated correctly.
        subfolder_count = len(src_file.relative_to(self.root_path).parts) - 1
        return HTML_TPL.format(
            title=src_file.stem,
            body=body,
            css_path="../" * subfolder_count + self._css_path_rel_doc,
        )

    def __call__(self, src, dst, *args, **kwargs):
        # Has same signature as shutil.copy(), for use with shutil.copytree().
        src = Path(src)
        if not self.convert_md or src.suffix.lower() != ".md":
            return shutil.copy2(src, dst, *args, **kwargs)
        dst = Path(dst)
        dst_filename = src.stem + ".htm"
        if dst.is_dir():
            dst = dst / dst_filename
        else:
            dst = dst.with_name(dst_filename)
        htm = self.md_to_html(src)
        with dst.open("w", encoding="utf8") as f:
            f.write(htm)
        self.converted_files[src] = dst
        return dst


def get_expected_help_index(fpkg_metadata: FMEPackageMetadata, format_directions=None):
    """
    Returns a mapping of the expected help contexts
    to the name of its corresponding HTML doc file,
    based on the formats and transformers in the given package metadata.

    Help contexts are keys used by FME Workbench to map help buttons in the UI
    to its corresponding page of documentation.
    The names of the expected HTML files follow a naming convention based on the help context.
    """
    # /foundation/ui/core/include/ui/core/helpkeywords.h
    index = {}
    if not format_directions:
        format_directions = {}
    fpkg_ident = f"{fpkg_metadata.publisher_uid}_{fpkg_metadata.uid}"
    # Each transformer has only one topic.
    for xformer in fpkg_metadata.transformers:
        index[f"fmx_{fpkg_ident}_{xformer.name}"] = f"/{xformer.name}.htm"
    # Each format has many topics.
    for fmt in fpkg_metadata.formats:
        fmt_ident = f"{fpkg_ident}_{fmt.name}".lower()
        directions = format_directions.get(fmt.name, "rw")
        # Format prefix is "rw" even when read-only or write-only
        index[f"rw_{fmt_ident}_index"] = f"/{fmt.name}.htm"
        index[f"rw_{fmt_ident}_feature_rep"] = f"/{fmt.name}_feature_rep.htm"
        for direction in directions:
            index[f"param_{fmt_ident}_{direction}"] = f"/{fmt.name}_param_{direction}.htm"
            index[f"ft_{fmt_ident}_param_{direction}"] = f"/{fmt.name}_ft_param_{direction}.htm"
        index[f"ft_{fmt_ident}_user_attr"] = f"/{fmt.name}_ft_user_attr.htm"
    return index


class HelpBuilder:
    def __init__(self, fpkg_metadata: FMEPackageMetadata, help_src_dir, help_dst_dir):
        self.fpkg_metadata = fpkg_metadata
        self.help_src_dir = Path(help_src_dir)
        self.help_dst_dir = Path(help_dst_dir)

    def build(self):
        """
        Copies help from src to dst.

        If the src has a package_help.csv, then switch to the "manual" mode
        where doc is copied as-is and package_help.csv is validated for correctness.

        If the src doesn't have package_help.csv, then all .md files are converted to .htm
        at the dst, and generate package_help.csv at the dst.
        To map help contexts to their doc, the Markdown files must follow a naming convention.
        """
        src_index_file = self.help_src_dir / "package_help.csv"
        copier = DocCopier(self.help_src_dir)
        for item in self.fpkg_metadata.transformers:
            copier.transformer_names.add(item.name)
        if src_index_file.is_file():
            self.validate_index(self.help_src_dir)
            copier.convert_md = False

        shutil.copytree(
            self.help_src_dir,
            self.help_dst_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*TREE_COPY_IGNORE_GLOBS),
            copy_function=copier,
        )
        if not (self.help_dst_dir / "package_help.csv").is_file():
            self.build_index(self.help_dst_dir)
        self.validate_index(self.help_dst_dir)

    def build_index(self, doc_dir):
        """
        Write package_help.csv based on package metadata and HTML help files present in doc_dir.
        To map help contexts to their doc, the Markdown files must follow a naming convention.
        Help contexts missing a doc file results in a warning,
        and its row omitted from the output.
        """
        expected = get_expected_help_index(self.fpkg_metadata)

        path = Path(doc_dir) / "package_help.csv"
        with path.open("w", encoding="utf8", newline="") as f:
            writer = csv.writer(f)
            for context in sorted(expected.keys()):
                expected_doc = Path(doc_dir) / expected[context][1:]  # Strip leading /
                if not expected_doc.is_file():
                    warnings.warn(f"Missing doc {expected_doc} ({context})")
                    continue
                writer.writerow([context, expected[context]])
        return path

    def validate_index(self, doc_dir):
        """
        Read package_help.csv and validates its contents. Checks that:

        - All expected help contexts are present, based on package metadata
        - No unrecognized help contexts are present
        - Referenced files exist and are HTML or MD
        """
        links = {}
        with (Path(doc_dir) / "package_help.csv").open("r", encoding="utf8", newline="") as f:
            try:
                for row in csv.reader(f):
                    links[row[0]] = row[1]
            except IndexError as e:
                raise IndexError("Invalid package_help.csv: must have 2 columns") from e
        for ctx, doc_path in links.items():
            if not doc_path.startswith("/"):
                raise ValueError(f"Path must start with /: {doc_path}")
            expected_doc = Path(doc_dir) / doc_path.lstrip("/")
            if not expected_doc.exists():
                raise FileNotFoundError(f"{expected_doc} does not exist")
            if expected_doc.suffix[1:].lower() not in ("htm", "html", "md"):
                raise ValueError(f"{expected_doc} must be htm(l) or md")
        expected = set(get_expected_help_index(self.fpkg_metadata).keys())
        contexts_present = set(links.keys())
        unrecognized = contexts_present - expected
        if unrecognized:
            raise ValueError(f"Unrecognized help: {', '.join(unrecognized)}")
        missing = expected - contexts_present
        if missing:
            raise ValueError(f"Missing help: {', '.join(missing)}")
