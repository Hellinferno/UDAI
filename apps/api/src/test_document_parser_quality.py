import sys
import types
from pathlib import Path

from openpyxl import Workbook

from tools import document_parser as dp


def test_financial_post_processing_extracts_priority_sections():
    text = "\n".join(
        [
            "Revenue from operations 12,345",
            "EBITDA margin 18.2%",
            "Total borrowings 4,200",
            "Cash and cash equivalents 1,100",
        ]
    )

    out = dp._post_process_financial_text(text)

    assert "### Financial Signals (Revenue, EBITDA, Debt, Cash)" in out
    assert "#### Revenue" in out
    assert "#### EBITDA" in out
    assert "#### Debt" in out
    assert "#### Cash" in out


def test_parse_pdf_uses_ocr_fallback_for_low_text_pages(monkeypatch, tmp_path: Path):
    class FakePage:
        def get_text(self, mode: str):
            if mode == "text":
                return ""
            if mode == "blocks":
                return []
            return ""

    class FakeDoc:
        def __iter__(self):
            return iter([FakePage()])

        def close(self):
            return None

    fake_fitz = types.SimpleNamespace(
        open=lambda _: FakeDoc(),
        Matrix=lambda x, y: (x, y),
    )

    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    tesseract_called = {"count": 0}
    rapid_called = {"count": 0}

    def fake_tesseract(_page):
        tesseract_called["count"] += 1
        return ""

    def fake_rapidocr(_page):
        rapid_called["count"] += 1
        return "Revenue from operations 999"

    monkeypatch.setattr(dp, "_ocr_page_with_tesseract", fake_tesseract)
    monkeypatch.setattr(dp, "_ocr_page_with_rapidocr", fake_rapidocr)

    fake_pdf = tmp_path / "scanned.pdf"
    fake_pdf.write_bytes(b"%PDF")

    out = dp.parse_document(str(fake_pdf), "pdf")

    assert tesseract_called["count"] == 1
    assert rapid_called["count"] == 1
    assert out is not None
    assert "Revenue from operations 999" in out
    assert "#### Revenue" in out


def test_parse_excel_emits_sheet_text_and_financial_signals(tmp_path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "P&L"
    ws.append(["Metric", "FY25"])
    ws.append(["Revenue from operations", 120000])
    ws.append(["EBITDA", 24000])
    ws.append(["Total borrowings", 18000])
    ws.append(["Cash and cash equivalents", 5000])

    xlsx_path = tmp_path / "financials.xlsx"
    wb.save(str(xlsx_path))

    out = dp.parse_document(str(xlsx_path), "xlsx")

    assert out is not None
    assert "## Sheet: P&L" in out
    assert "Revenue from operations" in out
    assert "#### Revenue" in out
    assert "#### EBITDA" in out
    assert "#### Debt" in out
    assert "#### Cash" in out
