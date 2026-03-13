import os
import re
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from models import APIResponse, Meta
from db_models import DealModel, DocumentModel
from dependencies import get_db, get_current_user
from database import SessionLocal
from tools.document_parser import parse_document

# Background parser pool: same as startup recovery
_parser_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doc_parse")

router = APIRouter(prefix="/deals/{deal_id}/documents", tags=["Documents"])

_UPLOAD_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads"
_UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "150"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Allowlisted extensions and their expected magic-byte prefixes.
# None means magic-bytes check is skipped (text-based formats).
_ALLOWED_TYPES: dict[str, Optional[bytes]] = {
    "pdf":  b"%PDF",
    "docx": b"PK\x03\x04",   # Office Open XML (ZIP)
    "xlsx": b"PK\x03\x04",
    "xls":  b"\xd0\xcf\x11\xe0",  # Compound Document (old Office)
    "csv":  None,
    "txt":  None,
    "json": None,
}

_SAFE_NAME_RE = re.compile(r"[^a-z0-9_.\-]")


def _parse_document_async(file_id: str, file_path: str, file_type: str):
    """Parse document in background and update database status."""
    try:
        parsed_text = parse_document(file_path, file_type)
        with SessionLocal() as db:
            doc = db.query(DocumentModel).get(file_id)
            if doc:
                doc.parsed_text = parsed_text
                doc.parse_status = "parsed" if parsed_text else "parse_failed"
                db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            doc = db.query(DocumentModel).get(file_id)
            if doc:
                doc.parse_status = "parse_failed"
                db.commit()
        print(f"[PARSE_ERROR] {file_id}: {exc}")


def _sanitize_filename(raw: str) -> str:
    """Return a safe filename: lowercase, only alphanumeric/dot/hyphen/underscore."""
    name = os.path.basename(raw or "upload").lower().replace(" ", "_")
    name = _SAFE_NAME_RE.sub("_", name)
    # Strip leading dots (hidden files) and limit length
    name = name.lstrip(".") or "upload"
    return name[:120]


def _magic_ok(content: bytes, ext: str) -> bool:
    """Verify first bytes match the expected signature for the declared extension."""
    expected = _ALLOWED_TYPES.get(ext)
    if expected is None:
        return True  # text-based; no magic bytes to check
    return content[: len(expected)] == expected


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    deal_id: str,
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    deal = db.query(DealModel).filter(
        DealModel.id == deal_id,
        DealModel.tenant_id == user["tenant_id"]
    ).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Validate category to prevent storing arbitrary strings
    if category and len(category) > 60:
        raise HTTPException(status_code=400, detail="Category too long")

    deal_upload_dir = _UPLOAD_BASE / deal_id
    deal_upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded_docs = []
    failed_docs = []

    for file in files:
        safe_filename = _sanitize_filename(file.filename or "upload")
        ext = safe_filename.rsplit(".", 1)[-1] if "." in safe_filename else "unknown"

        if ext not in _ALLOWED_TYPES:
            failed_docs.append({"filename": safe_filename, "reason": f"Unsupported file type: .{ext}"})
            continue

        # Read up to limit + 1 byte in memory BEFORE touching disk.
        # This prevents disk-filling attacks and avoids write-then-delete.
        content = await file.read(MAX_UPLOAD_BYTES + 1)

        if len(content) > MAX_UPLOAD_BYTES:
            failed_docs.append({
                "filename": safe_filename,
                "reason": f"File exceeds {MAX_UPLOAD_MB} MB limit",
            })
            continue

        if not _magic_ok(content, ext):
            failed_docs.append({
                "filename": safe_filename,
                "reason": f"File content does not match declared extension .{ext}",
            })
            continue

        file_id = str(uuid.uuid4())
        dest_path = deal_upload_dir / f"{file_id}_{safe_filename}"

        # Guard: resolved path must stay inside deal_upload_dir
        if not str(dest_path.resolve()).startswith(str(deal_upload_dir.resolve())):
            failed_docs.append({"filename": safe_filename, "reason": "Invalid filename"})
            continue

        try:
            dest_path.write_bytes(content)
        except OSError as exc:
            failed_docs.append({"filename": safe_filename, "reason": "Server error saving file"})
            print(f"[UPLOAD] OSError saving {safe_filename}: {exc}")
            continue

        new_doc = DocumentModel(
            id=file_id,
            deal_id=deal_id,
            filename=safe_filename,
            file_type=ext,
            file_size_bytes=len(content),
            storage_path=str(dest_path),
            doc_category=category,
            parse_status="parsing",
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # Queue parsing to run in background thread pool
        # This prevents the upload response from being blocked
        _parser_pool.submit(_parse_document_async, file_id, str(dest_path), ext)

        uploaded_docs.append({
            "id": new_doc.id,
            "filename": new_doc.filename,
            "file_type": new_doc.file_type,
            "file_size_bytes": new_doc.file_size_bytes,
            "parse_status": new_doc.parse_status,
            "uploaded_at": new_doc.uploaded_at.isoformat(),
        })

    if not uploaded_docs and failed_docs:
        detail = "; ".join(f"{item['filename']}: {item['reason']}" for item in failed_docs[:3])
        raise HTTPException(status_code=400, detail=detail)

    return APIResponse(
        success=True,
        data={"uploaded": uploaded_docs, "failed": failed_docs},
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}"),
    )


@router.get("", response_model=APIResponse)
async def list_documents(
    deal_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    deal = db.query(DealModel).filter(
        DealModel.id == deal_id,
        DealModel.tenant_id == user["tenant_id"]
    ).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    docs = db.query(DocumentModel).filter(DocumentModel.deal_id == deal_id).all()
    return APIResponse(
        success=True,
        data=[
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size_bytes": d.file_size_bytes,
                "doc_category": d.doc_category,
                "parse_status": d.parse_status,
                "uploaded_at": d.uploaded_at.isoformat(),
            }
            for d in docs
        ],
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}"),
    )


@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(
    deal_id: str, 
    doc_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    deal = db.query(DealModel).filter(
        DealModel.id == deal_id,
        DealModel.tenant_id == user["tenant_id"]
    ).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    doc = db.query(DocumentModel).filter(
        DocumentModel.id == doc_id,
        DocumentModel.deal_id == deal_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from filesystem
    doc_path = Path(doc.storage_path)
    # Safety: only delete if it's still inside the upload base
    try:
        if doc_path.resolve().is_relative_to(_UPLOAD_BASE.resolve()) and doc_path.exists():
            doc_path.unlink()
    except (ValueError, OSError):
        pass  # Log but don't expose internals

    db.delete(doc)
    db.commit()

    return APIResponse(
        success=True,
        data={"id": doc_id, "message": "Document deleted successfully"},
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}"),
    )
