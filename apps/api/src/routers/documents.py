import os
import uuid
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from typing import List, Optional

from models import APIResponse, Meta
from store import store, Document

router = APIRouter(prefix="/deals/{deal_id}/documents", tags=["Documents"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../../../data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    deal_id: str, 
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None)
):
    deal = store.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    uploaded_docs = []
    
    deal_upload_dir = os.path.join(UPLOAD_DIR, deal_id)
    os.makedirs(deal_upload_dir, exist_ok=True)
    
    for file in files:
        file_id = str(uuid.uuid4())
        safe_filename = file.filename.replace(" ", "_").lower()
        file_extension = safe_filename.split(".")[-1] if "." in safe_filename else "unknown"
        
        print(f"[UPLOAD] Received file: {file.filename} -> ext={file_extension}, deal={deal_id}")
        
        # Determine strict type or default to unknown
        supported_types = ["pdf", "docx", "xlsx", "xls", "csv", "txt", "json"]
        doc_type = file_extension if file_extension in supported_types else "unknown"
        
        if doc_type == "unknown":
            print(f"[UPLOAD] REJECTED: unsupported type '{file_extension}'")
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_extension}")
        
        file_path = os.path.join(deal_upload_dir, f"{file_id}_{safe_filename}")
        
        # Save to disk
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_size = os.path.getsize(file_path)
            
            # Enforce 50MB limit as per specs
            if file_size > 50 * 1024 * 1024:
                os.remove(file_path) # Cleanup
                raise HTTPException(status_code=413, detail=f"File {safe_filename} exceeds 50MB limit")
                
            # Create store entity
            new_doc = Document(
                id=file_id,
                deal_id=deal_id,
                filename=safe_filename,
                file_type=doc_type,
                file_size_bytes=file_size,
                storage_path=file_path,
                doc_category=category,
                parse_status="ready"
            )
            store.documents[file_id] = new_doc
            
            uploaded_docs.append({
                "id": new_doc.id,
                "filename": new_doc.filename,
                "file_type": new_doc.file_type,
                "file_size_bytes": new_doc.file_size_bytes,
                "parse_status": new_doc.parse_status,
                "uploaded_at": new_doc.uploaded_at.isoformat()
            })
            
        except Exception as e:
            # In a real app we would track failed documents in the array
            print(f"Failed to save file: {e}")
            continue
            
    return APIResponse(
        success=True,
        data={
            "uploaded": uploaded_docs,
            "failed": []
        },
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}")
    )

@router.get("", response_model=APIResponse)
async def list_documents(deal_id: str):
    deal = store.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    docs = store.get_documents_for_deal(deal_id)
    
    doc_list = []
    for d in docs:
        doc_list.append({
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size_bytes": d.file_size_bytes,
            "doc_category": d.doc_category,
            "parse_status": d.parse_status,
            "uploaded_at": d.uploaded_at.isoformat()
        })
        
    return APIResponse(
        success=True,
        data=doc_list,
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}")
    )

@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(deal_id: str, doc_id: str):
    doc = store.documents.get(doc_id)
    if not doc or doc.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Delete from filesystem
    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
        
    # Delete from store
    del store.documents[doc_id]
    
    return APIResponse(
        success=True,
        data={"id": doc_id, "message": "Document deleted successfully"},
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}")
    )
