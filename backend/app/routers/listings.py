from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user, get_current_user_optional
from ..models import (
    Category, Listing, ListingStatus, ListingType, Location, SavedListing, User, UserRole,
)
from ..schemas import (
    CategoryOut, ListingCreate, ListingOut, ListingPage, ListingUpdate, LocationOut,
)
from ..services.serializers import listing_out, rating_subquery

router = APIRouter(tags=["Marketplace"])

_LOAD = (joinedload(Listing.owner), joinedload(Listing.category), joinedload(Listing.location))


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _saved_ids(db: Session, user: User | None) -> set[int]:
    if user is None:
        return set()
    return set(db.scalars(select(SavedListing.listing_id).where(SavedListing.user_id == user.id)))


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.get("/locations", response_model=list[LocationOut])
def locations(db: Session = Depends(get_db)):
    return db.scalars(select(Location).order_by(Location.name)).all()


@router.get("/listings", response_model=ListingPage)
def search_listings(
    q: str | None = Query(None, max_length=100, description="Free-text search on title/description"),
    category_id: list[int] | None = Query(None, description="Repeat for multiple categories"),
    location_id: int | None = None,
    type: ListingType | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_rating: float | None = Query(None, ge=0, le=5),
    sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|rating)$"),
    mine: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    if mine and user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required to list your own listings")

    rs = rating_subquery()
    avg_col = func.coalesce(rs.c.avg_rating, 0)
    conds = []
    if mine:
        conds.append(Listing.owner_id == user.id)
    else:
        conds.append(Listing.status == ListingStatus.active)
    if q and q.strip():
        like = f"%{_escape_like(q.strip())}%"
        conds.append(Listing.title.ilike(like, escape="\\") | Listing.description.ilike(like, escape="\\"))
    if category_id:
        conds.append(Listing.category_id.in_(category_id))
    if location_id:
        conds.append(Listing.location_id == location_id)
    if type:
        conds.append(Listing.type == type)
    if min_price is not None:
        conds.append(Listing.price >= min_price)
    if max_price is not None:
        conds.append(Listing.price <= max_price)
    if min_rating:
        conds.append(avg_col >= min_rating)

    base = select(Listing.id).outerjoin(rs, rs.c.listing_id == Listing.id).where(*conds)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    order = {
        "newest": [Listing.created_at.desc(), Listing.id.desc()],
        "price_asc": [Listing.price.asc(), Listing.id.asc()],
        "price_desc": [Listing.price.desc(), Listing.id.asc()],
        "rating": [avg_col.desc(), Listing.id.asc()],
    }[sort]
    stmt = (
        select(Listing, rs.c.avg_rating, rs.c.review_count)
        .outerjoin(rs, rs.c.listing_id == Listing.id)
        .where(*conds)
        .options(*_LOAD)
        .order_by(*order)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = db.execute(stmt).all()
    saved = _saved_ids(db, user)
    return {
        "items": [listing_out(l, a, c, saved) for l, a, c in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _get_listing_row(db: Session, listing_id: int, user: User | None):
    rs = rating_subquery()
    row = db.execute(
        select(Listing, rs.c.avg_rating, rs.c.review_count)
        .outerjoin(rs, rs.c.listing_id == Listing.id)
        .where(Listing.id == listing_id)
        .options(*_LOAD)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    l, avg, cnt = row
    if l.status != ListingStatus.active and (
        user is None or (user.id != l.owner_id and user.role != UserRole.admin)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return l, avg, cnt


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(
    listing_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)
):
    l, avg, cnt = _get_listing_row(db, listing_id, user)
    return listing_out(l, avg, cnt, _saved_ids(db, user))


@router.post("/listings", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(data: ListingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Category, data.category_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category")
    if data.location_id and not db.get(Location, data.location_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown location")
    l = Listing(owner_id=user.id, **data.model_dump())
    db.add(l)
    db.commit()
    l, avg, cnt = _get_listing_row(db, l.id, user)
    return listing_out(l, avg, cnt)


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int, data: ListingUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if l.owner_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only edit your own listings")
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes and not db.get(Category, changes["category_id"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category")
    if changes.get("location_id") and not db.get(Location, changes["location_id"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown location")
    for k, v in changes.items():
        setattr(l, k, ListingStatus(v) if k == "status" else v)
    db.commit()
    l, avg, cnt = _get_listing_row(db, listing_id, user)
    return listing_out(l, avg, cnt, _saved_ids(db, user))


@router.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if l.owner_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own listings")
    db.delete(l)
    db.commit()


@router.post("/listings/{listing_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def save_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Listing, listing_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if not db.get(SavedListing, (user.id, listing_id)):
        db.add(SavedListing(user_id=user.id, listing_id=listing_id))
        db.commit()


@router.delete("/listings/{listing_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def unsave_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(SavedListing, (user.id, listing_id))
    if row:
        db.delete(row)
        db.commit()


@router.get("/users/me/saved", response_model=list[ListingOut])
def my_saved(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rs = rating_subquery()
    rows = db.execute(
        select(Listing, rs.c.avg_rating, rs.c.review_count)
        .join(SavedListing, SavedListing.listing_id == Listing.id)
        .outerjoin(rs, rs.c.listing_id == Listing.id)
        .where(SavedListing.user_id == user.id, Listing.status == ListingStatus.active)
        .options(*_LOAD)
        .order_by(SavedListing.created_at.desc())
    ).all()
    ids = {l.id for l, _, _ in rows}
    return [listing_out(l, a, c, ids) for l, a, c in rows]