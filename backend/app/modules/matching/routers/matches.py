from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select

from app.core.security import CurrentUser, DatabaseSession
from app.modules.matching.models.generation import MatchResult
from app.modules.matching.repositories.database import DatabaseMatchingStore
from app.modules.matching.schemas.contracts import Category as CategoryResponse
from app.modules.matching.schemas.contracts import MatchesQuery, MatchesResponse, MatchItem
from app.modules.matching.services.matches import get_matches
from app.modules.matching.services.search import SearchQuery, SearchResponse, search_posts
from app.modules.posts.models.post import Category
from app.shared.errors import DomainError

router = APIRouter(prefix="/api/v1", tags=["matching"])


class RecalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: UUID


def parse_query(request: Request, schema):
    values = {}
    for key, value in request.query_params.multi_items():
        if key not in schema.model_fields or key in values:
            code = "DUPLICATE_QUERY_PARAMETER" if key in values else "UNKNOWN_QUERY_PARAMETER"
            raise DomainError(
                422,
                code,
                "Query parameter is invalid",
                [{"field": key, "issue": "Use each supported query parameter at most once"}],
            )
        if key in ("page", "page_size") and not (value.isascii() and value.isdigit()):
            raise DomainError(
                422,
                "VALIDATION_ERROR",
                "Expected a positive integer",
                [{"field": key, "issue": "Expected an integer"}],
            )
        values[key] = value
    try:
        return schema.model_validate(values)
    except ValidationError as exc:
        raise DomainError(
            422,
            "VALIDATION_ERROR",
            "Query is invalid",
            [
                {"field": ".".join(map(str, error["loc"])) or "query", "issue": error["msg"]}
                for error in exc.errors()
            ],
        ) from None


def query_parameters(schema):
    spec = schema.model_json_schema()
    return {
        "parameters": [
            {
                "name": name,
                "in": "query",
                "required": name in spec.get("required", []),
                "schema": field,
            }
            for name, field in spec["properties"].items()
        ]
    }


@router.get("/categories")
def categories(db: DatabaseSession) -> list[CategoryResponse]:
    return [
        CategoryResponse(id=row.id, name=row.name)
        for row in db.scalars(
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.name, Category.id)
        )
    ]


@router.get("/search", openapi_extra=query_parameters(SearchQuery))
def search(request: Request, db: DatabaseSession) -> SearchResponse:
    return search_posts(db, parse_query(request, SearchQuery))


@router.get("/matches", openapi_extra=query_parameters(MatchesQuery))
def matches(request: Request, db: DatabaseSession) -> MatchesResponse:
    return get_matches(DatabaseMatchingStore(db), parse_query(request, MatchesQuery))


@router.post("/matches/recalculate")
def recalculate_matches(
    body: RecalculateRequest, db: DatabaseSession, user: CurrentUser
) -> MatchesResponse:
    store = DatabaseMatchingStore(db)
    store.recalculate(body.post_id, user.id, admin=user.role == "ADMIN")
    return get_matches(store, MatchesQuery(post_id=body.post_id))


@router.get("/matches/{id}")
def match_detail(id: UUID, db: DatabaseSession, post_id: UUID | None = Query(None)) -> MatchItem:
    stmt = select(MatchResult.source_id).where(MatchResult.id == id).order_by(MatchResult.source_id)
    if post_id is not None:
        stmt = stmt.where(MatchResult.source_id == post_id)
    store = DatabaseMatchingStore(db)
    for source_id in db.scalars(stmt).all():
        try:
            response = get_matches(store, MatchesQuery(post_id=source_id), match_id=id)
        except DomainError as exc:
            if exc.status not in (404, 409):
                raise
            continue
        if response.items:
            return response.items[0]
    raise DomainError(404, "MATCH_NOT_FOUND", "A current public match was not found")
