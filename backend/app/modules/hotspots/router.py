import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response

from app.core.security import CurrentAdmin, DatabaseSession
from app.modules.hotspots.schemas import (
    AlgorithmConfig,
    Analysis,
    ClusterDetail,
    ConfigPatch,
    HeatmapResponse,
    HotspotQuery,
    Statistics,
)

router = APIRouter(prefix="/api/ai/hotspots", tags=["Lost-item hotspots"])
admin = APIRouter(prefix="/api/admin/ai/hotspots", tags=["Admin hotspot analysis"])

Filters = Annotated[HotspotQuery, Query()]
ClusterId = Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")]


@router.get("")
def list_hotspots(request: Request, db: DatabaseSession, filters: Filters) -> Analysis:
    return request.app.state.hotspots.analyze(db, filters, "public").analysis


@router.get("/heatmap")
def heatmap(request: Request, db: DatabaseSession, filters: Filters) -> HeatmapResponse:
    snapshot = request.app.state.hotspots.analyze(db, filters, "public").analysis
    return HeatmapResponse(heatmap=snapshot.heatmap, is_demo=snapshot.is_demo)


@router.get("/statistics")
def statistics(request: Request, db: DatabaseSession, filters: Filters) -> Statistics:
    return request.app.state.hotspots.analyze(db, filters, "public").analysis.statistics


@router.get("/{cluster_id}")
def hotspot(
    request: Request, db: DatabaseSession, filters: Filters, cluster_id: ClusterId
) -> ClusterDetail:
    return request.app.state.hotspots.analyze(db, filters, "public").detail(cluster_id)


@admin.get("")
def admin_hotspots(
    request: Request, db: DatabaseSession, filters: Filters, user: CurrentAdmin
) -> Analysis:
    return request.app.state.hotspots.analyze(db, filters, "admin").analysis


@admin.get("/config")
def get_config(request: Request, db: DatabaseSession, user: CurrentAdmin) -> AlgorithmConfig:
    return request.app.state.hotspots.config(db)


@admin.patch("/config")
def update_config(
    request: Request, db: DatabaseSession, payload: ConfigPatch, user: CurrentAdmin
) -> AlgorithmConfig:
    return request.app.state.hotspots.update(db, payload)


@admin.post("/recalculate")
def recalculate(
    request: Request, db: DatabaseSession, filters: Filters, user: CurrentAdmin
) -> Analysis:
    request.app.state.ai.throttle("hotspot_recalculate", str(user.id))
    return request.app.state.hotspots.analyze(db, filters, "admin", force=True).analysis


@admin.get("/export")
def export(request: Request, db: DatabaseSession, filters: Filters, user: CurrentAdmin) -> Response:
    data = request.app.state.hotspots.analyze(db, filters, "admin").analysis
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["cluster_id", "area", "reports", "density", "from", "through", "demo"])
    for cluster in data.clusters:
        writer.writerow(
            [
                cluster.cluster_id,
                cluster.location_name,
                cluster.event_count,
                cluster.density_level,
                data.period.start_date,
                data.period.end_date,
                data.is_demo,
            ]
        )
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="findback-hotspots.csv"'},
    )


@admin.get("/{cluster_id}")
def admin_hotspot(
    request: Request,
    db: DatabaseSession,
    filters: Filters,
    cluster_id: ClusterId,
    user: CurrentAdmin,
) -> ClusterDetail:
    return request.app.state.hotspots.analyze(db, filters, "admin").detail(cluster_id)
