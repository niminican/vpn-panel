from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.package import Package
from app.schemas.package import PackageCreate, PackageUpdate, PackageResponse
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/api/packages", tags=["packages"])


def _pkg_response(pkg: Package) -> PackageResponse:
    dest_name = pkg.destination_vpn.name if pkg.destination_vpn else None
    return PackageResponse(
        id=pkg.id, name=pkg.name, description=pkg.description,
        bandwidth_limit=pkg.bandwidth_limit, speed_limit=pkg.speed_limit,
        duration_days=pkg.duration_days, max_connections=pkg.max_connections,
        price=float(pkg.price) if pkg.price is not None else None,
        currency=pkg.currency, enabled=pkg.enabled,
        destination_vpn_id=pkg.destination_vpn_id,
        destination_vpn_name=dest_name,
    )


@router.get("", response_model=list[PackageResponse])
def list_packages(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("packages.manage")),
):
    return [_pkg_response(p) for p in db.query(Package).all()]


@router.post("", response_model=PackageResponse, status_code=201)
def create_package(
    req: PackageCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("packages.manage")),
):
    pkg = Package(**req.model_dump())
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return _pkg_response(pkg)


@router.put("/{pkg_id}", response_model=PackageResponse)
def update_package(
    pkg_id: int,
    req: PackageUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("packages.manage")),
):
    pkg = db.query(Package).filter(Package.id == pkg_id).first()
    if not pkg:
        raise NotFoundError("Package")

    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(pkg, key, value)

    db.commit()
    db.refresh(pkg)
    return _pkg_response(pkg)


@router.delete("/{pkg_id}", status_code=204)
def delete_package(
    pkg_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("packages.manage")),
):
    pkg = db.query(Package).filter(Package.id == pkg_id).first()
    if not pkg:
        raise NotFoundError("Package")
    db.delete(pkg)
    db.commit()
