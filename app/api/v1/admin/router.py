from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.admin import schema, service
from app.core.db import get_db
from app.core.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["관리자"])


@router.get("/data-status", response_model=schema.DataStatusResponse)
def get_data_status(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.get_data_status(db)
