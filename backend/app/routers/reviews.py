"""RATINGS & REVIEWS"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Booking, BookingStatus, Listing, Review, User
from ..schemas import ReviewIn, ReviewOut, ReviewsOut
from ..services.serializers import user_brief

router = APIRouter(orefix="/reviews", tags=["Reviews"])


def _out (r: Review) -> dict:
    return {
        "id": r.id,
        "listing_id": r.listing_id,
        "rating": r.rating,
        "comment": r.comment,
        "reviewer": user_brief(r.reviewer),
        "created_at": r.created_at, 
    }
    
@router.get("", response_model=ReviewsOut)
def list_reviews(
    listing_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filt = [Review.listing_id == listing_id] if listing_id else []
    avg, cnt = db.execute(select(func.avg(Review.rating), func.count(Review.id)).where(*filt)).one()
    rows = db.scalars (
        select(Review).where(*filt)
        .options(joinedload(Review.reviewer), joinedload(Review.listing))
        .order_by(Review.created_at.desc(), Review.id.desc())
        .limit(limit)
    ).all()
    return {
        "average": round(float(avg), 1) if avg is not None else 0.0,
        "count": int(cnt or 0),
        "items" : [_out(r) for r in rows],
    }
    
@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing = db.get(Listing, data.listing_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot review your own listing")
    if db.scalar(select(Review.id).where(Review.listing_id == listing.id, Review.reviewer_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already reviewed this listing")
    if settings.require_booking_for_review and not db.scalar(
        select(Booking.id).where(
            Booking.listing_id == listing.id,
            Booking.requester_id == user.id,
            Booking.status == BookingStatus.completed,
        )
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only users with a completed booking can review this listing")
    r = Review(listing_id=listing.id, reviewer_id=user.id, rating=data.rating, comment=data.comment.strip())
    db.add(r)
    db.commit()
    return _out(
        db.scalars(
            select(Review).where(Review.id == r.id).options(joinedload(Review.reviewer), joinedload(Review.listing))
        ).one()
    )