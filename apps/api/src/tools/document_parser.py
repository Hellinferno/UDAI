"""
LlamaIndex-powered document parser.

Replaces the bare PyMuPDF/openpyxl ad-hoc extraction with LlamaIndex's
file readers so we get clean, structured text for every supported format:
  • PDF   – PDFReader  (wraps PyMuPDF / pdfminer, page-level text)
  • Excel – PandasExcelReader  (reads every sheet, preserves numbers)
  • CSV   – PandasCSVReader
  • DOCX  – DocxReader
  • TXT/JSON – plain read

The single public function `parse_document(path, file_type)` returns a
plain-text string that is stored in `Document.parsed_text`.
"""

from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_DOC_CHARS = int(os.environ.get("AIBAA_MAX_PARSED_CHARS", "1200000"))
_MAX_EXCEL_ROWS_PER_SHEET = int(os.environ.get("AIBAA_MAX_EXCEL_ROWS_PER_SHEET", "4000"))
_OCR_MIN_PAGE_CHARS = int(os.environ.get("AIBAA_OCR_MIN_PAGE_CHARS", "40"))

_NUMERIC_LINE_RE = re.compile(r"(?:\d[\d,\.\-]*%?)")
_SECTION_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "Revenue": (
        re.compile(r"\brevenue\b", re.I),
        re.compile(r"revenue\s+from\s+operations", re.I),
        re.compile(r"\bnet\s+sales\b", re.I),
        re.compile(r"\btotal\s+income\b", re.I),
    ),
    "EBITDA": (
        re.compile(r"\bebitda\b", re.I),
        re.compile(r"operating\s+profit", re.I),
        re.compile(r"profit\s+before\s+(?:interest|finance)\s+and\s+(?:tax|depreciation)", re.I),
    ),
    "Debt": (
        re.compile(r"\btotal\s+debt\b", re.I),
        re.compile(r"\bborrowings?\b", re.I),
        re.compile(r"lease\s+liabilit", re.I),
        re.compile(r"long[-\s]?term\s+debt", re.I),
        re.compile(r"short[-\s]?term\s+borrowings?", re.I),
    ),
    "Cash": (
        re.compile(r"cash\s+and\s+cash\s+equivalents", re.I),
        re.compile(r"\bcash\s+equivalents\b", re.I),
        re.compile(r"bank\s+balances", re.I),
        re.compile(r"current\s+investments", re.I),
        re.compile(r"liquid\s+investments", re.I),
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nodes_to_text(nodes) -> str:
    """Join LlamaIndex Document/Node objects into one string."""
    parts = []
    for node in nodes:
        text = getattr(node, "text", None) or getattr(node, "get_content", lambda: "")()
        if text and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _clean_text(text: str) -> str:
    """Normalize parser output while preserving line structure for tables."""
    if not text:
        return ""

    # Replace NULs and normalize common whitespace issues from OCR/PDFs.
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []
    for line in text.split("\n"):
        # Collapse internal whitespace but keep line breaks.
        collapsed = " ".join(line.split())
        if collapsed:
            cleaned_lines.append(collapsed)

    return "\n".join(cleaned_lines).strip()


def _clean_table_text(text: str) -> str:
    """Normalize table-heavy text while preserving tab-delimited structure."""
    if not text:
        return ""

    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines = []
    for line in text.split("\n"):
        if "\t" in line:
            cols = [" ".join(col.split()) for col in line.split("\t")]
            if any(cols):
                cleaned_lines.append("\t".join(cols).rstrip("\t"))
        else:
            collapsed = " ".join(line.split())
            if collapsed:
                cleaned_lines.append(collapsed)
    return "\n".join(cleaned_lines).strip()


def _truncate_text(text: str, max_chars: int = _MAX_DOC_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return f"{text[:max_chars]}\n\n[...truncated {omitted:,} chars for context window safety...]"


def _safe_cell_to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        # Keep financial precision sane without noisy long tails.
        as_int = int(value)
        return str(as_int) if value == as_int else f"{value:.6g}"
    return str(value).strip()


_RAPIDOCR_ENGINE = None


def _ocr_page_with_tesseract(page) -> str:
    """OCR one PDF page via pytesseract. Returns empty string on failure."""
    try:
        import fitz  # type: ignore
        import pytesseract
        from PIL import Image

        matrix = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        ocr_lang = os.environ.get("AIBAA_OCR_LANG", "eng")
        ocr_config = os.environ.get("AIBAA_OCR_CONFIG", "--oem 3 --psm 6")
        text = pytesseract.image_to_string(img, lang=ocr_lang, config=ocr_config)
        return _clean_text(text)
    except Exception as exc:
        logger.warning("Tesseract OCR unavailable/failed: %s", exc)
        return ""


def _ocr_page_with_rapidocr(page) -> str:
    """OCR one PDF page via RapidOCR (pure Python/ONNX runtime)."""
    global _RAPIDOCR_ENGINE
    try:
        import fitz  # type: ignore
        import numpy as np
        from PIL import Image
        from rapidocr_onnxruntime import RapidOCR

        if _RAPIDOCR_ENGINE is None:
            _RAPIDOCR_ENGINE = RapidOCR()

        matrix = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img_arr = np.array(img)

        result, _ = _RAPIDOCR_ENGINE(img_arr)
        if not result:
            return ""

        lines = []
        for item in result:
            # RapidOCR tuple shape: [box, text, score]
            if len(item) >= 2:
                text = str(item[1]).strip()
                if text:
                    lines.append(text)
        return _clean_text("\n".join(lines))
    except Exception as exc:
        logger.warning("RapidOCR fallback failed: %s", exc)
        return ""


def _ocr_page_with_fallback(page) -> str:
    """Try OCR backends in order: Tesseract -> RapidOCR."""
    text = _ocr_page_with_tesseract(page)
    if text:
        return text
    return _ocr_page_with_rapidocr(page)


def _post_process_financial_text(text: str) -> str:
    """Prepend a compact financial-signals block for key valuation fields."""
    if not text:
        return text

    section_hits: dict[str, list[str]] = {k: [] for k in _SECTION_PATTERNS}
    section_seen: dict[str, set[str]] = {k: set() for k in _SECTION_PATTERNS}

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if not _NUMERIC_LINE_RE.search(line):
            continue

        for section, patterns in _SECTION_PATTERNS.items():
            if any(p.search(line) for p in patterns):
                key = line.lower()
                if key not in section_seen[section]:
                    section_seen[section].add(key)
                    section_hits[section].append(line)
                break

    summary_lines = ["### Financial Signals (Revenue, EBITDA, Debt, Cash)"]
    any_signal = False
    for section in ("Revenue", "EBITDA", "Debt", "Cash"):
        hits = section_hits[section][:15]
        if not hits:
            continue
        any_signal = True
        summary_lines.append(f"#### {section}")
        for item in hits:
            summary_lines.append(f"- {item}")

    if not any_signal:
        return text

    summary = "\n".join(summary_lines)
    return f"{summary}\n\n{text}"


# ---------------------------------------------------------------------------
# Per-format parsers
# ---------------------------------------------------------------------------

def _parse_pdf(path: Path) -> str:
    # Use PyMuPDF directly — much faster and more reliable than pypdf for
    # complex financial PDFs.  LlamaIndex PDFReader wraps pypdf which hangs
    # on large / scanned PDFs, so we skip it here.
    try:
        import fitz  # type: ignore  (PyMuPDF)
        doc = fitz.open(str(path))
        pages = []
        ocr_pages = 0
        for idx, page in enumerate(doc, start=1):
            # Primary extraction.
            page_text = page.get_text("text") or ""

            # Fallback for pages where plain-text mode returns sparse output.
            if len(page_text.strip()) < 80:
                blocks = page.get_text("blocks") or []
                block_lines = []
                for block in blocks:
                    if len(block) >= 5:
                        block_text = str(block[4]).strip()
                        if block_text:
                            block_lines.append(block_text)
                page_text = "\n".join(block_lines)

            # OCR fallback for scanned/low-text pages.
            if len(page_text.strip()) < _OCR_MIN_PAGE_CHARS:
                ocr_text = _ocr_page_with_fallback(page)
                if ocr_text:
                    page_text = ocr_text
                    ocr_pages += 1

            cleaned = _clean_text(page_text)
            if cleaned:
                pages.append(f"## Page {idx}\n{cleaned}")

        # Free native resources ASAP.
        doc.close()
        text = "\n\n".join(pages)
        if text.strip():
            if ocr_pages:
                logger.info("PDF OCR fallback used for %d pages in %s", ocr_pages, path.name)
            return _truncate_text(_post_process_financial_text(text))
    except Exception as exc:
        logger.error("PyMuPDF PDF parse failed: %s", exc)

    return ""


def _parse_excel(path: Path) -> str:
    # openpyxl-first for better sheet/header fidelity in financial models.
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        sheets = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                cells = [_safe_cell_to_str(c) for c in row]
                if any(c for c in cells):
                    rows.append("\t".join(cells))
                    row_count += 1
                    if row_count >= _MAX_EXCEL_ROWS_PER_SHEET:
                        rows.append("[...rows truncated for context window safety...]")
                        break
            if rows:
                sheets.append(f"## Sheet: {sheet_name}\n" + "\n".join(rows))
        wb.close()
        text = "\n\n".join(sheets)
        if text.strip():
            return _truncate_text(_post_process_financial_text(_clean_table_text(text)))
    except Exception as exc:
        logger.warning("openpyxl Excel parse failed (%s), trying LlamaIndex", exc)

    # Fallback: LlamaIndex reader
    try:
        from llama_index.readers.file import PandasExcelReader
        reader = PandasExcelReader(concat_rows=False)
        docs = reader.load_data(file=path)
        text = _nodes_to_text(docs)
        text = _clean_table_text(text)
        if text.strip():
            return _truncate_text(_post_process_financial_text(text))
    except Exception as exc:
        logger.error("LlamaIndex PandasExcelReader failed: %s", exc)

    return ""


def _parse_xls(path: Path) -> str:
    """Legacy .xls via pandas (xlrd)."""
    try:
        import pandas as pd
        xl = pd.ExcelFile(str(path))
        parts = []
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            if len(df) > _MAX_EXCEL_ROWS_PER_SHEET:
                df = df.head(_MAX_EXCEL_ROWS_PER_SHEET)
            parts.append(f"## Sheet: {sheet}\n{df.to_string(index=False)}")
        return _truncate_text(_post_process_financial_text(_clean_table_text("\n\n".join(parts))))
    except Exception as exc:
        logger.error(".xls parse failed: %s", exc)
        return ""


def _parse_csv(path: Path) -> str:
    try:
        from llama_index.readers.file import PandasCSVReader
        reader = PandasCSVReader()
        docs = reader.load_data(file=path)
        text = _nodes_to_text(docs)
        if text.strip():
            return _truncate_text(_post_process_financial_text(_clean_table_text(text)))
    except Exception as exc:
        logger.warning("LlamaIndex PandasCSVReader failed (%s), falling back to pandas", exc)

    try:
        import pandas as pd
        df = pd.read_csv(str(path))
        if len(df) > _MAX_EXCEL_ROWS_PER_SHEET:
            df = df.head(_MAX_EXCEL_ROWS_PER_SHEET)
        return _truncate_text(_post_process_financial_text(_clean_table_text(df.to_string(index=False))))
    except Exception as exc:
        logger.error("CSV parse failed: %s", exc)
        return ""


def _parse_docx(path: Path) -> str:
    try:
        from llama_index.readers.file import DocxReader
        reader = DocxReader()
        docs = reader.load_data(file=path)
        text = _nodes_to_text(docs)
        if text.strip():
            return text
    except Exception as exc:
        logger.warning("LlamaIndex DocxReader failed (%s), falling back to python-docx", exc)

    try:
        from docx import Document as DocxDocument  # type: ignore
        doc = DocxDocument(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return _truncate_text(_clean_text("\n\n".join(paragraphs)))
    except Exception as exc:
        logger.error("python-docx parse failed: %s", exc)
        return ""


def _parse_text(path: Path) -> str:
    try:
        return _truncate_text(_post_process_financial_text(_clean_text(path.read_text(encoding="utf-8", errors="replace"))))
    except Exception as exc:
        logger.error("Text read failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PARSERS = {
    "pdf":  _parse_pdf,
    "xlsx": _parse_excel,
    "xls":  _parse_xls,
    "csv":  _parse_csv,
    "docx": _parse_docx,
    "txt":  _parse_text,
    "json": _parse_text,
}


def parse_document(storage_path: str, file_type: str) -> Optional[str]:
    """
    Parse a document file and return its text content.

    Parameters
    ----------
    storage_path : absolute path to the file on disk
    file_type    : lowercase extension without dot (pdf, xlsx, csv, ...)

    Returns the extracted text, or None if parsing failed.
    """
    path = Path(storage_path)
    if not path.exists():
        logger.error("parse_document: file not found: %s", storage_path)
        return None

    parser = _PARSERS.get(file_type.lower())
    if parser is None:
        logger.warning("parse_document: unsupported type '%s'", file_type)
        return None

    try:
        text = parser(path)
        logger.info(
            "parse_document: parsed %s (%s) → %d chars",
            path.name, file_type, len(text)
        )
        return text if text else None
    except Exception as exc:
        logger.exception("parse_document: unexpected error for %s: %s", storage_path, exc)
        return None
