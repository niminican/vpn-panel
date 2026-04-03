from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.setting import Setting
from app.schemas.setting import SettingUpdate, SettingResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "global_alerts_enabled": "true",
    "alert_email_enabled": "false",
    "alert_telegram_enabled": "true",
    "bandwidth_poll_interval": "60",
    "connection_logging_enabled": "true",
    "panel_language": "en",
}


@router.get("", response_model=list[SettingResponse])
def list_settings(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("settings.manage")),
):
    settings = db.query(Setting).all()
    existing_keys = {s.key for s in settings}

    # Add defaults for missing settings
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            s = Setting(key=key, value=value)
            db.add(s)
            settings.append(s)

    db.commit()
    return settings


@router.put("")
def update_settings(
    updates: list[SettingUpdate],
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("settings.manage")),
):
    for update in updates:
        setting = db.query(Setting).filter(Setting.key == update.key).first()
        if setting:
            setting.value = update.value
        else:
            db.add(Setting(key=update.key, value=update.value))

    db.commit()
    return {"ok": True}
