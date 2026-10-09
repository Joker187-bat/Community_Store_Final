# Helpers for ORM rows(turns rows into dict shapes)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Listing, Review, User

def user_brief(u: user) - > dict:
    return {"id": u.id, "full_name": u.full_name, "role": u.role.value, "is_verified": u.is_verified}


def listing_brief(l: Listing) -> dict:
    return {"id": l.id, "title": l.title, "icon": l.icon}

def rating_subquery():
    # avg + count of reviews per listing
    return (
        select (
            Review.listing_id.label("listing_id"),
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .group_by(Review.listing_id)
        .subquery()
    )
    
def listing_out(l: Listing, avg, count, saved_ids: set[int] | None = None) -> dict:
    return {
        "id": l.id,
        "title": l.title,
        "description": l.description,
        "price": float(l.price),
        "price_unit": l.price_unit,
        "condition": l.condition,
        "icon": l.icon,
        "type": l.type.value,
        "status": l.status.value,
        "category": {"id": l.category.id, "name": l.category.name, "icon": l.category.icon},
        "location": {"id": l.category.id, "name": l.category.name} if l.location else None,
        "owner": user_brief(l.owner),
        "avg_rating": round(float(avg), 1) if avg is not None else 0.0,
        "review__count": int(count or 0),
        "is_saved": bool(saved_ids and l.id in saved_ids),
        "created_at": l.created_at,
    }
    
    