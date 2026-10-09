from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..models import Conversation, Listing, Message, User
from ..schemas import ConversationOut, ConversationStart, MessageIn, MessageOut
from ..services.serializers import user_brief

router = APIRouter(prefix="/conversations", tags=["Messaging"])


def _participant_or_404(db: Session, conv_id: int, user: User) -> Conversation:
    c = db.scalars(
        select(Conversation)
        .where(Conversation.id == conv_id)
        .options(joinedload(Conversation.user_a), joinedload(Conversation.user_b), joinedload(Conversation.listing))
    ).first()
    if c is None or user.id not in (c.user_a_id, c.user_b_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return c


def _summary(db: Session, c: Conversation, me: User) -> dict:
    other = c.user_b if c.user_a_id == me.id else c.user_a
    last = db.scalars(
        select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at.desc(), Message.id.desc()).limit(1)
    ).first()
    unread = db.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == c.id, Message.sender_id != me.id, Message.is_read.is_(False)
        )
    )
    return {
        "id": c.id,
        "listing_id": c.listing_id,
        "listing_title": c.listing.title if c.listing else None,
        "other_user": user_brief(other),
        "last_message": last.body if last else None,
        "last_message_at": last.created_at if last else c.created_at,
        "unread_count": int(unread or 0),
    }


@router.get("", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convs = db.scalars(
        select(Conversation)
        .where(or_(Conversation.user_a_id == user.id, Conversation.user_b_id == user.id))
        .options(joinedload(Conversation.user_a), joinedload(Conversation.user_b), joinedload(Conversation.listing))
    ).all()
    out = [_summary(db, c, user) for c in convs]
    out.sort(key=lambda s: s["last_message_at"], reverse=True)
    return out


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def start_conversation(data: ConversationStart, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing = None
    recipient_id = data.recipient_id
    if data.listing_id is not None:
        listing = db.get(Listing, data.listing_id)
        if listing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
        recipient_id = listing.owner_id
    if recipient_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide listing_id or recipient_id")
    if recipient_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot message yourself")
    recipient = db.get(User, recipient_id)
    if recipient is None or not recipient.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")

    a, b = sorted((user.id, recipient_id))
    stmt = select(Conversation).where(Conversation.user_a_id == a, Conversation.user_b_id == b)
    stmt = stmt.where(Conversation.listing_id.is_(None) if listing is None else Conversation.listing_id == listing.id)
    conv = db.scalars(stmt).first()
    if conv is None:
        conv = Conversation(user_a_id=a, user_b_id=b, listing_id=listing.id if listing else None)
        db.add(conv)
        db.flush()
    db.add(Message(conversation_id=conv.id, sender_id=user.id, body=data.body))
    db.commit()
    return _summary(db, _participant_or_404(db, conv.id, user), user)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _participant_or_404(db, conversation_id, user)
    db.execute(
        update(Message)
        .where(Message.conversation_id == c.id, Message.sender_id != user.id, Message.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return db.scalars(
        select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at, Message.id)
    ).all()


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    conversation_id: int, data: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    c = _participant_or_404(db, conversation_id, user)
    m = Message(conversation_id=c.id, sender_id=user.id, body=data.body)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m