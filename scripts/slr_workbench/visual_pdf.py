"""Visual PDF conversion adapted from xtobando/slr-system (MIT)."""

import hashlib
import html
import json
import math
import os
import re
import shutil
import tempfile
import unicodedata
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path


class EngineError(ValueError):
    """A safe PDF conversion error."""


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode("utf-8") if isinstance(content, str) else content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def markdown_text(text):
    """Keep extracted PDF text literal, including HTML and Markdown punctuation."""
    text = re.sub(r"([\\`*_{}\[\]#!|~$])", r"\\\1", html.escape(text, quote=False))
    text = re.sub(
        r"^(\s*)([-+]|\d+[.)])(?=\s|$)",
        lambda match: match[1] + match[2][:-1] + "\\" + match[2][-1],
        text,
    )
    return re.sub(r"^(\s*)(=+|-+)(\s*)$", r"\1\\\2\3", text)


def pdf_visual_regions(page, blocks):
    """Find convenient crops; full-page rendering remains the coverage guarantee."""
    import pymupdf as fitz

    regions, warnings = [], []
    try:
        regions.extend(("image", fitz.Rect(item["bbox"])) for item in page.get_image_info())
        for rectangle in page.cluster_drawings(x_tolerance=6, y_tolerance=6):
            rectangle = fitz.Rect(rectangle)
            # Include intersecting labels, which are usually separate PDF text objects.
            for block in blocks:
                box = fitz.Rect(block["bbox"])
                if rectangle.intersects(box):
                    rectangle |= box
            regions.append(("vector", rectangle))
    except (RuntimeError, ValueError) as exc:
        warnings.append(
            f"Graphic crop detection incomplete ({type(exc).__name__}); inspect the full-page image."
        )
    for block in blocks:
        spans = [span for line in block.get("lines", []) for span in line["spans"]]
        text = " ".join(span["text"] for span in spans)
        math_font = any(
            re.search(r"math|symbol|cmsy|cmmi|cmex|stix", span.get("font", ""), re.IGNORECASE)
            for span in spans
        )
        if (
            math_font
            or any(unicodedata.category(char) == "Sm" for char in text)
            or any(span.get("flags", 0) & 1 for span in spans)
        ):
            # Whole blocks preserve fraction bars and adjacent super/subscripts better
            # than individual text spans. This is detection, not formula transcription.
            regions.append(("formula", fitz.Rect(block["bbox"])))
    return regions, warnings


def convert_pdf(pdf, output_dir, dpi=300, crops=None):
    """Export a local PDF without constructing Engine or altering review evidence.

    All asset boxes use unrotated page coordinates in PDF points. The PDF stays
    authoritative: crops are heuristic and no OCR or LaTeX is inferred here.
    A new destination is published only after the complete export succeeds.
    """
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise EngineError("Install the 'visual' extra to render PDF pages.") from exc
    pdf, output_dir = Path(pdf).resolve(), Path(output_dir).resolve()
    if not pdf.is_file():
        raise EngineError("Input PDF does not exist or is not a file.")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 600:
        raise EngineError("PDF conversion DPI must be an integer from 72 to 600.")
    if output_dir.exists():
        raise EngineError(
            "Output directory already exists; choose a new --output-dir to preserve existing work."
        )
    digest = file_sha256(pdf)
    try:
        document = fitz.open(pdf)
    except (RuntimeError, ValueError) as exc:
        raise EngineError("Cannot open input as a valid PDF.") from exc
    with document:
        if not document.is_pdf or document.needs_pass or not len(document):
            raise EngineError("PDF is empty, password-protected, or invalid.")
        manual = defaultdict(list)
        for crop in crops or []:
            if len(crop) != 5 or not all(math.isfinite(value) for value in crop):
                raise EngineError("Each --crop needs PAGE X0 Y0 X1 Y1 with finite numbers.")
            number, x0, y0, x1, y1 = crop
            if number != int(number) or not 1 <= number <= len(document) or x1 <= x0 or y1 <= y0:
                raise EngineError(
                    "Crop requires a valid one-based page and an ordered, nonempty rectangle."
                )
            page = document[int(number) - 1]
            box = fitz.Rect(x0, y0, x1, y1)
            if not (page.rect * page.derotation_matrix).contains(box):
                raise EngineError("Crop lies outside the unrotated visible page bounds.")
            manual[int(number)].append(box)
        # Check every page before allocating large pixmaps or publishing any files.
        for page in document:
            if (
                math.ceil(page.rect.width * dpi / 72) * math.ceil(page.rect.height * dpi / 72)
                > 80_000_000
            ):
                raise EngineError(
                    "PDF page exceeds the 80-million-pixel render budget; choose a lower --dpi."
                )
        manifest = {
            "converter": "PyMuPDF",
            "converter_version": version("PyMuPDF"),
            "schema_version": 1,
            "source": {"filename": pdf.name, "sha256": digest},
            "dpi": dpi,
            "coordinate_system": "unrotated PDF points; top-left origin",
            "pages": [],
        }
        pieces = [
            (
                f"# {markdown_text(pdf.stem)}\n\n<!-- PDF_SHA256: {digest} -->\n\n"
                "Text is extracted from the PDF; reading order and mathematical text may be imperfect. "
                "Formulas and graphics are preserved visually. Crops are candidates, not an exhaustive "
                "classification; every page also has a full-page image. No OCR or LaTeX transcription "
                "has been performed. Check the original PDF for authoritative detail.\n"
            )
        ]
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".pdf-export-", dir=output_dir.parent) as temporary:
            staging = Path(temporary) / "output"
            staging.mkdir()
            shutil.copyfile(pdf, staging / "original.pdf")
            if file_sha256(staging / "original.pdf") != digest:
                raise EngineError("Source PDF changed while archiving.")
            for number, page in enumerate(document, 1):
                bounds = page.rect * page.derotation_matrix
                blocks = [
                    block
                    for block in page.get_text(
                        "dict", sort=True, flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
                    )["blocks"]
                    if block["type"] == 0
                ]
                has_text = any(
                    span["text"].strip()
                    for block in blocks
                    for line in block["lines"]
                    for span in line["spans"]
                )
                regions, warnings = pdf_visual_regions(page, blocks)
                entry = {
                    "page": number,
                    "width": bounds.width,
                    "height": bounds.height,
                    "rotation": page.rotation,
                    "text_status": "extracted" if has_text else "no_text",
                    "assets": [],
                    "warnings": warnings,
                }

                def render(kind, box, filename, page=page, entry=entry, number=number):
                    # Text/graphics boxes are unrotated; pixmap clips are rotated.
                    clip = box * page.rotation_matrix
                    pixmap = page.get_pixmap(dpi=dpi, clip=clip, alpha=False, colorspace=fitz.csRGB)
                    atomic_write(staging / filename, pixmap.tobytes("png"))
                    entry["assets"].append({"kind": kind, "path": filename, "bbox": list(box)})
                    return f"![{kind.capitalize()} reference, page {number}]({filename})"

                full_page = render("page", bounds, f"page_{number}_visual.png")
                events = []
                for block in blocks:
                    lines = [
                        "".join(span["text"] for span in line["spans"]) for line in block["lines"]
                    ]
                    text = "  \n".join(markdown_text(line) for line in lines).strip()
                    if text:
                        events.append((block["bbox"][1], block["bbox"][0], 0, text))
                counters, seen = Counter(), set()
                if len(regions) > 150:
                    warnings.append(
                        "Automatic crops limited to 150 on this page; inspect the full-page image."
                    )
                candidates = regions[:150] + [("manual", box) for box in manual[number]]
                for kind, rectangle in candidates:
                    padding = 4 if kind != "manual" else 0
                    box = (rectangle + (-padding, -padding, padding, padding)) & bounds
                    if box.is_empty or box.is_infinite:
                        continue
                    identity = (kind, *(round(value, 2) for value in box))
                    if identity in seen:
                        continue
                    seen.add(identity)
                    counters[kind] += 1
                    link = render(kind, box, f"page_{number}_{kind}_{counters[kind]}.png")
                    events.append((box.y0, box.x0, 1, link))
                pieces.append(f"<!-- page: {number} -->\n\n## Page {number}\n")
                pieces.extend(item[3] + "\n" for item in sorted(events))
                if not has_text:
                    pieces.append(
                        "No extractable text on this page; inspect the image (scanned or blank page).\n"
                    )
                pieces.extend("> " + warning + "\n" for warning in warnings)
                pieces.append("### Full-page reference\n\n" + full_page + "\n")
                manifest["pages"].append(entry)
            if file_sha256(pdf) != digest:
                raise EngineError("Source PDF changed during conversion; retry with a stable copy.")
            atomic_write(staging / "fulltext.md", "\n".join(pieces))
            atomic_write(
                staging / "assets.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
            )
            if output_dir.exists():
                raise EngineError(
                    "Output directory appeared during conversion; existing work was preserved."
                )
            staging.rename(output_dir)
    return {
        "original": str(output_dir / "original.pdf"),
        "markdown": str(output_dir / "fulltext.md"),
        "manifest": str(output_dir / "assets.json"),
        "pages": len(manifest["pages"]),
        "images": sum(len(page["assets"]) for page in manifest["pages"]),
    }
