from __future__ import annotations

from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader
from pptx import Presentation

from app.models.schemas import ExecutionResult


class DocumentReaderTool:
    def preview(self, target: str) -> ExecutionResult:
        candidate = Path(target).expanduser()
        if candidate.exists() and candidate.is_file():
            return self._read_file(candidate)

        return ExecutionResult(
            success=True,
            message=f"No concrete file path resolved for '{target}'.",
            details=["Provide a full path or ask the assistant to find the file first."],
        )

    def _read_file(self, path: Path) -> ExecutionResult:
        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md", ".py", ".json"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                return self._summarize_text(path, text)
            if suffix == ".csv":
                text = path.read_text(encoding="utf-8", errors="ignore")
                return self._summarize_text(path, text)
            if suffix == ".pdf":
                reader = PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages[:5])
                return self._summarize_text(path, text)
            if suffix == ".docx":
                doc = Document(str(path))
                text = "\n".join(p.text for p in doc.paragraphs[:50])
                return self._summarize_text(path, text)
            if suffix == ".pptx":
                prs = Presentation(str(path))
                slides = []
                for slide in prs.slides[:10]:
                    fragments = [shape.text for shape in slide.shapes if hasattr(shape, "text") and shape.text]
                    slides.append(" ".join(fragments))
                return self._summarize_text(path, "\n".join(slides))
            if suffix in {".xlsx", ".xlsm"}:
                workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
                details = []
                for sheet in workbook.sheetnames[:3]:
                    ws = workbook[sheet]
                    rows = list(ws.iter_rows(min_row=1, max_row=5, values_only=True))
                    details.append(f"Sheet {sheet}: {rows}")
                return ExecutionResult(success=True, message=f"Read workbook {path.name}.", details=details)
        except Exception as exc:
            return ExecutionResult(success=False, message=f"Failed to read {path.name}: {exc}")

        return ExecutionResult(
            success=True,
            message=f"Unsupported file type for {path.name}.",
            details=["Supported: txt, md, pdf, docx, pptx, xlsx, csv"],
        )

    def _summarize_text(self, path: Path, text: str) -> ExecutionResult:
        normalized = " ".join(text.split())
        preview = normalized[:600] if normalized else "No readable text found."
        return ExecutionResult(success=True, message=f"Read {path.name}.", details=[preview])
