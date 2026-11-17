from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError

from ..repositories.snapshots import SnapshotReader
from ..schemas.contracts import ErrorResponse, MatchesQuery, MatchesResponse
from ..services.matches import MatchingError, get_matches

router = APIRouter(prefix="/api/v1", tags=["matching"])


class QueryError(MatchingError):
    def __init__(self, code, details):
        super().__init__(422, code, "Query không hợp lệ.")
        self.details = details


def parse_query(request: Request) -> MatchesQuery:
    counts = Counter(key for key, _ in request.query_params.multi_items())
    for key in sorted(counts):
        if key not in MatchesQuery.model_fields:
            raise QueryError("UNKNOWN_QUERY_PARAMETER", [{"field": key, "code": "UNKNOWN_QUERY_PARAMETER", "message": "Tham số không được hỗ trợ."}])
        if counts[key] > 1:
            raise QueryError("DUPLICATE_QUERY_PARAMETER", [{"field": key, "code": "DUPLICATE_QUERY_PARAMETER", "message": "Tham số chỉ được xuất hiện một lần."}])
    data = dict(request.query_params)
    # Pydantic accepts '1.0' as an int; query contract deliberately disallows it.
    invalid_ints = [key for key in ("page", "page_size") if key in data and not (data[key].isascii() and data[key].isdigit())]
    try:
        result = MatchesQuery.model_validate(data)
    except ValidationError as exc:
        errors = {str(error["loc"][0]): {"field": str(error["loc"][0]), "code": "REQUIRED" if error["type"] == "missing" else "INVALID_VALUE", "message": "Trường bắt buộc." if error["type"] == "missing" else "Giá trị không hợp lệ."} for error in exc.errors()}
    else:
        errors = {}
    for key in invalid_ints:
        errors[key] = {"field": key, "code": "INVALID_VALUE", "message": "Phải là số nguyên."}
    if errors:
        raise QueryError("VALIDATION_ERROR", [errors[key] for key in sorted(errors)])
    return result


def get_reader(request: Request) -> SnapshotReader:
    return request.app.state.matching_reader


@router.get("/matches", response_model=MatchesResponse,
            openapi_extra={"parameters": [
                {"name": key, "in": "query", "required": key == "post_id", "schema": schema}
                for key, schema in MatchesQuery.model_json_schema()["properties"].items()
            ]},
            responses={status: {"model": ErrorResponse} for status in (404, 409, 422, 500, 503)})
def matches(query: Annotated[MatchesQuery, Depends(parse_query)], reader: Annotated[SnapshotReader, Depends(get_reader)]):
    return get_matches(reader, query)
