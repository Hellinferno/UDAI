import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db_models import DealModel, OutputModel
from dependencies import get_db, get_current_user
from store import store
from models import APIResponse, Meta

# Resolve the base output directory; FileResponse paths are validated against it.
_OUTPUT_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "outputs"

# Two routers: one for deal-scoped output listing, one for direct download.
deal_router = APIRouter(prefix="/deals", tags=["Outputs"])
output_router = APIRouter(prefix="/outputs", tags=["Outputs"])

@deal_router.get("/{deal_id}/outputs", response_model=APIResponse)
async def list_deal_outputs(
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
        
    outputs = db.query(OutputModel).filter(OutputModel.deal_id == deal_id).all()
    
    outputs_list = []
    for out in outputs:
        outputs_list.append({
            "id": out.id,
            "agent_run_id": out.agent_run_id,
            "filename": out.filename,
            "output_type": out.output_type,
            "output_category": out.output_category,
            "review_status": out.review_status,
            "created_at": out.created_at.isoformat()
        })
            
    return APIResponse(
        success=True,
        data=outputs_list,
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}")
    )

@output_router.get("/{output_id}/download")
async def download_output(
    output_id: str,
    db: Session = Depends(get_db),
    # Note: Downloading outputs might need different auth handling for static tokens, linking to user for now
    user: dict = Depends(get_current_user)
):
    output_record = db.query(OutputModel).get(output_id)
    if not output_record:
        raise HTTPException(status_code=404, detail="Output not found")
        
    # Tenant verification
    deal = db.query(DealModel).filter(
        DealModel.id == output_record.deal_id,
        DealModel.tenant_id == user["tenant_id"]
    ).first()
    if not deal:
        raise HTTPException(status_code=403, detail="Access denied for tenant")

    file_path = Path(output_record.storage_path).resolve()

    # Guard against path-traversal: only serve files within allowed output roots.
    upload_base = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads"
    allowed_roots = (_OUTPUT_BASE.resolve(), upload_base.resolve())
    # Use Path.is_relative_to-style check via str comparison with trailing sep to
    # prevent prefix-collision attacks (e.g. /data/outputs-evil).
    def _within(fp: Path, root: Path) -> bool:
        try:
            fp.relative_to(root)
            return True
        except ValueError:
            return False
    if not any(_within(file_path, root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical file missing from disk")

    return FileResponse(
        path=str(file_path),
        filename=output_record.filename,
        media_type="application/octet-stream",
    )
