from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.models.alert import Alert
from app.schemas.setting import AlertResponse
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    query = db.query(Alert)
    if unread_only:
        query = query.filter(Alert.acknowledged == False)  # noqa: E712
    return query.order_by(Alert.sent_at.desc()).offset(skip).limit(limit).all()


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise NotFoundError("Alert")
    alert.acknowledged = True
    db.commit()
    return {"ok": True}


@router.post("/acknowledge-all")
def acknowledge_all_alerts(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    db.query(Alert).filter(Alert.acknowledged == False).update(  # noqa: E712
        {"acknowledged": True}
    )
    db.commit()
    return {"ok": True}
