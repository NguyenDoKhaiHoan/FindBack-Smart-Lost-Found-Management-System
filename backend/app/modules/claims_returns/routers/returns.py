from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.core.security import CurrentUser, DatabaseSession
from app.modules.claims_returns.schemas.claims import ApproveClaimRequest, ClaimDetail
from app.modules.claims_returns.schemas.returns import (
    AddEvidenceRequest,
    ArrangeReturnRequest,
    ReturnView,
)
from app.modules.claims_returns.services import returns

router = APIRouter(prefix="/api/v1", tags=["Claims and returns"])


@router.post("/claims/{id}/evidence", status_code=201)
def add_evidence(
    id: UUID, body: AddEvidenceRequest, request: Request, db: DatabaseSession, user: CurrentUser
) -> ClaimDetail:
    return returns.add_evidence(db, id, user.id, body, request.app.state.settings.media_root)


@router.get("/claims/{id}/evidence/{evidence_id}/file", response_class=FileResponse)
def download_evidence(
    id: UUID, evidence_id: UUID, request: Request, db: DatabaseSession, user: CurrentUser
):
    path, mime = returns.evidence_file(
        db, id, evidence_id, user.id, request.app.state.settings.media_root
    )
    return FileResponse(
        path,
        media_type=mime,
        filename="claim-evidence",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/returns", status_code=201)
def arrange_return(
    body: ArrangeReturnRequest, db: DatabaseSession, user: CurrentUser
) -> ReturnView:
    return returns.arrange_return(db, body, user.id)


@router.get("/returns/{id}")
def read_return(id: UUID, db: DatabaseSession, user: CurrentUser) -> ReturnView:
    return ReturnView.model_validate(returns.get_return(db, id, user.id))


@router.patch("/returns/{id}/handover")
def record_handover(
    id: UUID, body: ApproveClaimRequest, db: DatabaseSession, user: CurrentUser
) -> ReturnView:
    return returns.mark_handover(db, id, user.id, body.expected_version)
