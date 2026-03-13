import uuid
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from db_models import DealModel, DocumentModel, AgentRunModel
from dependencies import get_db, get_current_user
from models import APIResponse, Meta
from agents.orchestrator import OrchestratorAgent
from agents.modeling import FinancialModelingAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deals", tags=["Agents"])


class AgentRunPayload(BaseModel):
    agent_type: str = Field(..., min_length=1, max_length=40)
    task_name: str = Field(..., min_length=1, max_length=80)
    parameters: Dict[str, Any] = Field(default_factory=dict)

@router.post("/{deal_id}/agents/run", response_model=APIResponse)
async def dispatch_agent(
    deal_id: str, 
    payload: AgentRunPayload,
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
    if any(d.parse_status in ("pending", "parsing") for d in docs):
        raise HTTPException(status_code=422, detail="Cannot run agent while documents are still processing.")

    try:
        # Initialize the Orchestrator which acts as the main routing brain
        orchestrator = OrchestratorAgent(
            deal_id=deal_id,
            input_payload=payload.model_dump()
        )
        orch_id = orchestrator.run()

        orchestrator_record = db.query(AgentRunModel).get(orch_id)
        if not orchestrator_record:
            raise HTTPException(status_code=500, detail="Orchestrator run record not found")

        if orchestrator_record.status != "completed":
            raise HTTPException(
                status_code=422,
                detail=orchestrator_record.error_message or "Routing failed"
            )

        route = orchestrator_record.input_payload.get("route_decision", {})
        target_agent = route.get("target_agent")
        target_task = route.get("target_task")

        if target_agent == "modeling" and target_task == "dcf_model":
            specialized_payload = payload.model_dump()
            specialized_payload["agent_type"] = target_agent
            specialized_payload["task_name"] = target_task
            specialized_agent = FinancialModelingAgent(deal_id, specialized_payload)
            run_id = specialized_agent.run()
        else:
            run_id = orch_id
            
        # Fetch the resulting run log from the db
        run_record = db.query(AgentRunModel).get(run_id)
        
        return APIResponse(
            success=True,
            data={
                "run_id": run_id,
                "status": run_record.status if run_record else "unknown",
                "steps": run_record.reasoning_steps if run_record else [],
                "route": route,
                "valuation_result": run_record.input_payload.get("valuation_result") if run_record else None
            },
            meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}")
        )
        
    except Exception as e:
        logger.exception("Agent dispatch failed for deal %s", deal_id)
        raise HTTPException(status_code=500, detail="Agent execution failed. Check server logs for details.")

@router.get("/{deal_id}/agents/runs", response_model=APIResponse)
async def list_agent_runs(
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
        
    runs = db.query(AgentRunModel).filter(AgentRunModel.deal_id == deal_id).all()
    
    return APIResponse(
        success=True,
        data={
            "runs": [
                {
                    "run_id": run.id,
                    "agent_type": run.agent_type,
                    "task_name": run.task_name,
                    "status": run.status,
                    "created_at": run.created_at.isoformat()
                } for run in runs
            ]
        },
        meta=Meta(request_id=f"req_{uuid.uuid4().hex[:8]}")
    )
