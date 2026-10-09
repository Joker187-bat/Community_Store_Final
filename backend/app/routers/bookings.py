from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..models import Booking, BookingStatus, Listing, ListingStatus, User
from ..schemas import BookingCreate, BookingOut, BookingStatusIn
from ..services.serializers import listing_brief, user_brief

router = APIRouter(prefix="/bookings", tags=["Bookings"])

TRANSITIONS = {
    ("provider", BookingStatus.pending): {BookingStatus.accepted, BookingStatus.declined},
    ("provider", BookingStatus.accepted): {BookingStatus.completed},
    ("requester", BookingStatus.pending): {BookingStatus.cancelled},
    ("requester", BookingStatus.accepted): {BookingStatus.cancelled},
}

_LOAD = (joinedload(Booking.listing).joinedload(Listing.owner), joinedload(Booking.requester))


def _out(b: Booking) -> dict:
    return {
        "id": b.id,
        "listing": listing_brief(b.listing),
        "requester": user_brief(b.requester),
        "provider": user_brief(b.listing.owner),
        "preferred_date": b.preferred_date,
        "preferred_time": b.preferred_time,
        "notes": b.notes,
        "status": b.status.value,
        "created_at": b.created_at,
    }


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(data: BookingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing = db.get(Listing, data.listing_id)
    if listing is None or listing.status != ListingStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found or no longer available")
    if listing.owner_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot send a request to your own listing")
    duplicate = db.scalar(
        select(Booking.id).where(
            Booking.listing_id == listing.id,
            Booking.requester_id == user.id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.accepted]),
        )
    )
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have an open request for this listing")
    b = Booking(listing_id=listing.id, requester_id=user.id, **data.model_dump(exclude={"listing_id"}))
    db.add(b)
    db.commit()
    return _out(db.scalars(select(Booking).where(Booking.id == b.id).options(*_LOAD)).one())


@router.get("/mine", response_model=list[BookingOut])
def my_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(Booking).where(Booking.requester_id == user.id).options(*_LOAD).order_by(Booking.created_at.desc())
    ).all()
    return [_out(b) for b in rows]


@router.get("/received", response_model=list[BookingOut])
def received_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(Booking)
        .join(Listing, Listing.id == Booking.listing_id)
        .where(Listing.owner_id == user.id)
        .options(*_LOAD)
        .order_by(Booking.created_at.desc())
    ).all()
    return [_out(b) for b in rows]


@router.patch("/{booking_id}/status", response_model=BookingOut)
def change_status(
    booking_id: int, data: BookingStatusIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    b = db.scalars(select(Booking).where(Booking.id == booking_id).options(*_LOAD)).first()
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if user.id == b.listing.owner_id:
        side = "provider"
    elif user.id == b.requester_id:
        side = "requester"
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not part of this booking")
    new = BookingStatus(data.status)
    if new not in TRANSITIONS.get((side, b.status), set()):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A {side} cannot change a {b.status.value} booking to {new.value}"
        )
    b.status = new
    db.commit()
    return _out(b)