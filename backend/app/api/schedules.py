from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.models.user import User
from app.models.schedule import UserSchedule
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.core.exceptions import NotFoundError
from app.services.iptables import apply_time_schedule, remove_time_schedule

router = APIRouter(prefix="/api/users/{user_id}/schedules", tags=["schedules"])


def _sync_schedule_rules(user: User, db: Session):
    """Sync iptables time schedule rules for a user."""
    schedules = db.query(UserSchedule).filter(
        UserSchedule.user_id == user.id,
        UserSchedule.enabled == True,  # noqa: E712
    ).all()

    rules = [
        {
            "day_of_week": s.day_of_week,
            "start_time": s.start_time,
            "end_time": s.end_time,
        }
        for s in schedules
    ]
    try:
        if rules:
            apply_time_schedule(user.id, user.assigned_ip, rules)
        else:
            remove_time_schedule(user.id, user.assigned_ip)
    except Exception:
        pass


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")
    return db.query(UserSchedule).filter(UserSchedule.user_id == user_id).all()


@router.post("", response_model=ScheduleResponse, status_code=201)
def add_schedule(
    user_id: int,
    req: ScheduleCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    schedule = UserSchedule(
        user_id=user_id,
        day_of_week=req.day_of_week,
        start_time=req.start_time,
        end_time=req.end_time,
        enabled=req.enabled,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    _sync_schedule_rules(user, db)
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    user_id: int,
    schedule_id: int,
    req: ScheduleCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    schedule = db.query(UserSchedule).filter(
        UserSchedule.id == schedule_id,
        UserSchedule.user_id == user_id,
    ).first()
    if not schedule:
        raise NotFoundError("Schedule")

    schedule.day_of_week = req.day_of_week
    schedule.start_time = req.start_time
    schedule.end_time = req.end_time
    schedule.enabled = req.enabled
    db.commit()
    db.refresh(schedule)

    _sync_schedule_rules(user, db)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    user_id: int,
    schedule_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    schedule = db.query(UserSchedule).filter(
        UserSchedule.id == schedule_id,
        UserSchedule.user_id == user_id,
    ).first()
    if not schedule:
        raise NotFoundError("Schedule")

    db.delete(schedule)
    db.commit()

    _sync_schedule_rules(user, db)
