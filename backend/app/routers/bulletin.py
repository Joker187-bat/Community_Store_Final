from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_current_user_optional
from ..models import BulletinPost, PostFlag, PostStatus, User, UserRole
from ..schemas import FlagIn, PostIn, PostOut
from ..services.serializers import user_brief

router = APIRouter(prefix="/bulletin", tags=["Bulletin Board"])


def _flag_counts(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(PostFlag.post_id, func.count(PostFlag.id)).where(PostFlag.post_id.in_(ids)).group_by(PostFlag.post_id)
    ).all()
    return {pid: int(n) for pid, n in rows}


def post_out(p: BulletinPost, flags: dict[int, int], me: User | None) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "body": p.body,
        "status": p.status.value,
        "author": user_brief(p.author),
        "flag_count": flags.get(p.id, 0),
        "is_mine": bool(me and me.id == p.author_id),
        "created_at": p.created_at,
    }


@router.get("", response_model=list[PostOut])
def feed(mine: bool = False, db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)):
    if mine and user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    stmt = select(BulletinPost).options(joinedload(BulletinPost.author))
    if mine:
        stmt = stmt.where(BulletinPost.author_id == user.id, BulletinPost.status != PostStatus.removed)
    else:
        stmt = stmt.where(BulletinPost.status == PostStatus.active)
    posts = db.scalars(stmt.order_by(BulletinPost.created_at.desc(), BulletinPost.id.desc()).limit(100)).all()
    flags = _flag_counts(db, [p.id for p in posts])
    return [post_out(p, flags, user) for p in posts]


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(data: PostIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = BulletinPost(author_id=user.id, title=data.title.strip(), body=data.body.strip())
    db.add(p)
    db.commit()
    p = db.scalars(select(BulletinPost).where(BulletinPost.id == p.id).options(joinedload(BulletinPost.author))).one()
    return post_out(p, {}, user)


@router.post("/{post_id}/flag", status_code=status.HTTP_202_ACCEPTED)
def flag_post(post_id: int, data: FlagIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(BulletinPost, post_id)
    if p is None or p.status == PostStatus.removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    if p.author_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot flag your own post")
    if db.scalar(select(PostFlag.id).where(PostFlag.post_id == p.id, PostFlag.reporter_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already flagged this post")
    db.add(PostFlag(post_id=p.id, reporter_id=user.id, reason=data.reason.strip()))
    db.flush()
    count = db.scalar(select(func.count(PostFlag.id)).where(PostFlag.post_id == p.id)) or 0
    hidden = False
    if count >= settings.flag_threshold and p.status == PostStatus.active:
        p.status = PostStatus.flagged
        hidden = True
    db.commit()
    return {"detail": "Post flagged for moderation", "flag_count": int(count), "hidden": hidden}


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(BulletinPost, post_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    if p.author_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own posts")
    db.delete(p)
    db.commit()