from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedLoad

from ..database import get_db
from ..deps import require_admin
from ..models import Booking, BulletinPost, Listing, Message, PostFlag, PostStatus, Review, User
from ..schemas import PostOut, StatsOut, UserOut
from .bulletin import _flag_counts, post_out

router = APIRouter (prefix="/admin", tags = ["Administration"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=StatsOut)
def stats (db: Session = Depends(get_db)):
    def n (model, *where):
        return int(db,scalar(select(func.count()).select_from(model).where(*where)) or 0)
    
    return {
        "users": n(User),
        "unverified_users": n(User, User.is_verified.is_(False)),
        "listings": n(Listing),
        "bookings": n(Booking),
        "messages": n(Message),
        "reviews": n(Review),
        "posts": n(BulletinPost),
        "flagged_posts": n(BulletinPost, BulletinPost.status == PostStatus.flagged),
    }
    
@router.get("/users/unverified", response_model=list[UserOut])
def unverified_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.is_verified.is_(False), User.is_active.is_(True)).order_by(User.created_at)).all()

@router.get("/posts/flagged", response_model=list[PostOut])
def flagged_posts(db: Session = Depends(get_db), admin:User = Depends(require_admin)):
    posts = db.scalars (
        select(BulletinPost)
        .where (BulletinPost.status == PostStatus.flagged)
        .options(joinedLoad(BulletinPost.author))
        .order_by(BulletinPost.created_at.desc())
    ).all()
    flags = _flag_counts(db, [p.id for p in posts])
    return [post_out(p, flags, admin)for p in posts]

@router.post("/posts/{post_id}/restore", response_model=PostOut)
def restore_post (post_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = db.scalars(select(BulletinPost).where(BulletinPost.id == post_id).options(joinedLoad(BulletinPost.author))).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    for f in db.scalars(select(PostFlag).where(PostFlag.post_id == p.id)):
        db.delete(f)
    p.status = PostStatus.active
    db.commit()
    return post_out(p, {}, admin)

@router.post("/posts/{post_id}/remove", response_model=PostOut)
def remove_post(post_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = db.scalars(select(BulletinPost).where(BulletinPost.id == post_id).options(joinedload(BulletinPost.author))).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    p.status = PostStatus.removed
    db.commit()
    return post_out(p, _flag_counts(db, [p.id]), admin)