from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.admin import schema, service
from app.core.db import get_db
from app.core.deps import require_admin


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["어드민"],
    dependencies=[Depends(require_admin)],
)


@router.get("/data-status", response_model=schema.DataStatusResponse)
def data_status(
    db: Session = Depends(get_db),
):
    return service.get_data_status(db)


@router.get("/audience-insights", response_model=schema.AudienceInsightsResponse)
def audience_insights():
    return service.get_audience_insights()
