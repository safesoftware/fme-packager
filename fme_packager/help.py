"""
Logic for preparing help documentation for the FPKG packing process.

- package_help.csv validation
- File copy logic for the help folder
- Markdown to HTML conversion and package_help.csv generation
"""
import csv
import shutil
import warnings
from pathlib import Path

from markdown import Markdown
from markdown.extensions.toc import TocExtension

from fme_packager.metadata import FMEPackageMetadata
from fme_packager.operations import TREE_COPY_IGNORE_GLOBS


class DocCopier:
    """
    Callable with the same signature as shutil.copy2(), for use with shutil.copytree().
    Copies files while converting MD files to HTML at the destination.
    Identical to shutil.copy2() when conversion is disabled.
    """

    def __init__(self):
        self.convert_md = True
        self.converted_files = {}
        self._md_converter = Markdown(
            extensions=["tables", "fenced_code", TocExtension(toc_depth="2-3", title="Contents")],
        )

    def md_to_html(self, text):
        return self._md_converter.reset().convert(text)

    def __call__(self, src, dst, *args, **kwargs):
        # Has same signature as shutil.copy(), for use with shutil.copytree().
        src = Path(src)
        if self.convert_md and src.suffix.lower() == ".md":
            dst = Path(dst)
            dst_filename = src.stem + ".htm"
            if dst.is_dir():
                dst = dst / dst_filename
            else:
                dst = dst.with_name(dst_filename)
            with src.open("r", encoding="utf8") as f:
                htm = self.md_to_html(f.read())
            with dst.open("w", encoding="utf8") as f:
                f.write(htm)
            self.converted_files[src] = dst
            return dst
        return shutil.copy2(src, dst, *args, **kwargs)


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
        index[f"fmx_{fpkg_ident}_{xformer.name}"] = f"{xformer.name}.htm"
    # Each format has many topics.
    for fmt in fpkg_metadata.formats:
        fmt_ident = f"{fpkg_ident}_{fmt.name}".lower()
        directions = format_directions.get(fmt.name, "rw")
        # Format prefix is "rw" even when read-only or write-only
        index[f"rw_{fmt_ident}_index"] = f"{fmt.name}.htm"
        index[f"rw_{fmt_ident}_feature_rep"] = f"{fmt.name}_feature_rep.htm"
        for direction in directions:
            index[f"param_{fmt_ident}_{direction}"] = f"{fmt.name}_param_{direction}.htm"
            index[f"ft_{fmt_ident}_param_{direction}"] = f"{fmt.name}_ft_param_{direction}.htm"
        index[f"ft_{fmt_ident}_user_attr"] = f"{fmt.name}_ft_user_attr.htm"
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
        copier = DocCopier()
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
                expected_doc = Path(doc_dir) / expected[context]
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
