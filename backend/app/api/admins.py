import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin, ALL_PERMISSIONS
from app.models.admin_audit_log import AdminAuditLog
from app.schemas.admin import (
    AdminCreate,
    AdminUpdate,
    AdminResponse,
    AdminAuditLogResponse,
    AuditLogListResponse,
)
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError
from app.services.audit_logger import log_action

router = APIRouter(prefix="/api/admins", tags=["admins"])


def _require_super_admin(admin: Admin):
    if not admin.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")


def _admin_to_response(admin: Admin) -> AdminResponse:
    return AdminResponse(
        id=admin.id,
        username=admin.username,
        role=admin.role,
        permissions=admin.get_permissions(),
        created_at=admin.created_at,
    )


@router.get("/permissions")
def list_available_permissions(
    _admin: Admin = Depends(get_current_admin),
):
    """List all available permissions."""
    return {"permissions": ALL_PERMISSIONS}


@router.get("/me", response_model=AdminResponse)
def get_current_admin_info(
    admin: Admin = Depends(get_current_admin),
):
    """Get current admin's info including role and permissions."""
    return _admin_to_response(admin)


@router.get("", response_model=list[AdminResponse])
def list_admins(
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    _require_super_admin(admin)
    admins = db.query(Admin).order_by(Admin.created_at.asc()).all()
    return [_admin_to_response(a) for a in admins]


@router.post("", response_model=AdminResponse, status_code=201)
def create_admin(
    req: AdminCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    _require_super_admin(admin)

    if db.query(Admin).filter(Admin.username == req.username).first():
        raise ConflictError("Username already exists")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Validate permissions
    invalid = set(req.permissions) - set(ALL_PERMISSIONS)
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid permissions: {invalid}")

    new_admin = Admin(
        username=req.username,
        password_hash=hash_password(req.password),
        role=req.role if req.role in ("admin", "super_admin") else "admin",
        permissions=json.dumps(req.permissions) if req.permissions else None,
    )
    db.add(new_admin)
    log_action(db, admin, "create_admin", "admin", details=f"Created admin {req.username} (role={req.role})",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(new_admin)
    return _admin_to_response(new_admin)


@router.put("/{admin_id}", response_model=AdminResponse)
def update_admin(
    admin_id: int,
    req: AdminUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    _require_super_admin(admin)

    target = db.query(Admin).filter(Admin.id == admin_id).first()
    if not target:
        raise NotFoundError("Admin")

    if req.username and req.username != target.username:
        if db.query(Admin).filter(Admin.username == req.username).first():
            raise ConflictError("Username already exists")
        target.username = req.username

    if req.password:
        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        target.password_hash = hash_password(req.password)

    if req.role is not None:
        target.role = req.role if req.role in ("admin", "super_admin") else "admin"

    if req.permissions is not None:
        invalid = set(req.permissions) - set(ALL_PERMISSIONS)
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid permissions: {invalid}")
        target.permissions = json.dumps(req.permissions)

    log_action(db, admin, "update_admin", "admin", resource_id=admin_id,
               details=f"Updated admin {target.username}",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(target)
    return _admin_to_response(target)


@router.delete("/{admin_id}", status_code=204)
def delete_admin(
    admin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    _require_super_admin(admin)

    target = db.query(Admin).filter(Admin.id == admin_id).first()
    if not target:
        raise NotFoundError("Admin")

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    log_action(db, admin, "delete_admin", "admin", resource_id=admin_id,
               details=f"Deleted admin {target.username}",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    db.delete(target)
    db.commit()


# ─── Audit Logs ─────────────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin_username: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """List admin audit logs. Super admin only."""
    _require_super_admin(admin)

    query = db.query(AdminAuditLog)
    if admin_username:
        query = query.filter(AdminAuditLog.admin_username.like(f"%{admin_username}%"))
    if action:
        query = query.filter(AdminAuditLog.action == action)

    total = query.count()
    logs = query.order_by(AdminAuditLog.created_at.desc()).offset(skip).limit(limit).all()

    return AuditLogListResponse(
        logs=[AdminAuditLogResponse.model_validate(log) for log in logs],
        total=total,
    )
