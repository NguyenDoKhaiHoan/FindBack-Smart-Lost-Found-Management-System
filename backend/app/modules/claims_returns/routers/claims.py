from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_session
from app.modules.claims_returns.schemas.claims import (
    ApproveClaimRequest,
    ClaimDetail,
    ClaimPage,
    ClaimQuery,
    ClaimSummary,
    CompleteClaimRequest,
    CreateClaimRequest,
    NoQuery,
    RejectClaimRequest,
)
from app.modules.claims_returns.services.claims import ClaimService
from app.modules.identity.models.user import User
from app.shared.errors import ApiError, DomainError

Actor = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_session)]
router = APIRouter(
    prefix="/api/v1/claims",
    tags=["Claims"],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422)},
)


async def reject_get_body(request: Request):
    if await request.body():
        raise DomainError(422, "VALIDATION_ERROR", "GET requests must not contain a body")


@router.post("", status_code=201, response_model=ClaimSummary, summary="Tạo yêu cầu nhận đồ")
def create_claim(
    body: CreateClaimRequest,
    actor: Actor,
    session: Database,
    response: Response,
    query: Annotated[NoQuery, Query()],
):
    result = ClaimService(session).create(actor.id, body)
    response.headers["Location"] = f"/api/v1/claims/{result.id}"
    return result


@router.get(
    "/me",
    response_model=ClaimPage,
    summary="Danh sách yêu cầu liên quan đến tôi",
    dependencies=[Depends(reject_get_body)],
)
def list_my_claims(actor: Actor, session: Database, query: Annotated[ClaimQuery, Query()]):
    return ClaimService(session).list_me(actor.id, query)


@router.get(
    "/{id}",
    response_model=ClaimDetail,
    summary="Chi tiết và bằng chứng theo quyền",
    dependencies=[Depends(reject_get_body)],
)
def get_claim(
    id: UUID,
    actor: Actor,
    session: Database,
    query: Annotated[NoQuery, Query()],
):
    return ClaimService(session).detail(actor.id, id)


@router.patch("/{id}/approve", response_model=ClaimSummary, summary="Chủ tin chấp nhận yêu cầu")
def approve_claim(
    id: UUID,
    body: ApproveClaimRequest,
    actor: Actor,
    session: Database,
    query: Annotated[NoQuery, Query()],
):
    return ClaimService(session).approve(actor.id, id, body)


@router.patch("/{id}/reject", response_model=ClaimSummary, summary="Chủ tin từ chối yêu cầu")
def reject_claim(
    id: UUID,
    body: RejectClaimRequest,
    actor: Actor,
    session: Database,
    query: Annotated[NoQuery, Query()],
):
    return ClaimService(session).reject(actor.id, id, body)


@router.patch(
    "/{id}/complete", response_model=ClaimSummary, summary="Người nhận xác nhận đã nhận đồ"
)
def complete_claim(
    id: UUID,
    body: CompleteClaimRequest,
    actor: Actor,
    session: Database,
    query: Annotated[NoQuery, Query()],
):
    return ClaimService(session).complete(actor.id, id, body)
