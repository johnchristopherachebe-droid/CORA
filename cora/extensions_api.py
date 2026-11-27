"""Optional FastAPI router factory. Host app supplies auth dependency and configured services."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

class ResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=200)

class ProposalRequest(BaseModel):
    path: str = Field(min_length=1, max_length=240)
    proposed_content: str = Field(max_length=300000)

def build_router(*, require_owner, research_workspace, upgrade_manager):
    router = APIRouter(prefix="/cora", tags=["CORA extensions"])

    @router.post("/research")
    def research(body: ResearchRequest, _owner=Depends(require_owner)):
        try:
            return research_workspace.create(body.query, body.title)
        except Exception as exc:
            raise HTTPException(400, "Research request could not be completed") from exc

    @router.get("/research")
    def research_list(_owner=Depends(require_owner)):
        return {"items": research_workspace.list()}

    @router.get("/research/{session_id}")
    def research_get(session_id: str, _owner=Depends(require_owner)):
        try:
            return research_workspace.get(session_id)
        except KeyError as exc:
            raise HTTPException(404, "Research session not found") from exc

    @router.post("/upgrade/proposals")
    def upgrade_propose(body: ProposalRequest, _owner=Depends(require_owner)):
        try:
            item = upgrade_manager.propose(body.path, body.proposed_content)
            return {"proposal_id": item.proposal_id, "path": item.relative_path, "diff": item.diff,
                    "base_sha256": item.base_sha256, "status": item.status}
        except Exception as exc:
            raise HTTPException(400, "Upgrade proposal could not be created") from exc

    return router
