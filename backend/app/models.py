# ORM models that mirror backend/db/schema.sql (PostGreSQL DDL)
import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum as SAEnum, ForeignKey, Integer,
    Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

class UserRole(str, enum.Enum):
    student = "student"
    faculty = "faculty"
    vendor = "vendor"
    resident = "resident"
    admin = "admin"
    
class ListingType(str, enum.Enum):
    product = "product"
    service = "service"

class ListingStatus(str, enum.Enum):
    active = "active"
    sold = "sold"
    hidden = "hidden"
    

class BookingStatus(str,enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    cancelled = "cancelled"
    completed = "completed"
    
class PostStatus(str, enum.Enum):
    active = "active"
    flagged = "flagged"
    removed = "removed"
    
def pg_enum(enum_cls, name: str):
    #Stores enum values and reuses the PostGreSQL type created
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


def ts():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name : Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), default=UserRole.student)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = ts()
    
    listings: Mapped [list["listing"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    

class Category(Base):
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    icon: Mapped[str] = mapped_column(String(8), default="📦")
    

class Location(Base):
    __tablename__ = "locations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    

class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_listing_price"),)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"),index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True, nullable=True)
    type: Mapped[ListingType] = mapped_column(pg_enum(ListingType, "listing_type"), default=ListingType.product)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 20))
    price_unit: Mapped[str] = mapped_column(String(20), default="")
    condition: Mapped[int] = mapped_column(String(30), default="")
    icon: Mapped[int] = mapped_column(String(8), default= "📦")
    status: Mapped[ListingStatus] = mapped_column(
    pg_enum(ListingStatus, "listing_status"), default=ListingStatus.active, index=True    
    )
    created_at: Mapped[datetime] = ts()
    
    owner: Mapped[User] = relationship(back_populates="listings")
    category: Mapped[Category] = relationship()
    location: Mapped[Location | None] = relationship()
    
class SavedListing(Base):
    __tablename__ = "saved_listings"
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = ts()
    
    
class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"), index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[BookingStatus] = mapped_column (
        pg_enum(BookingStatus, "booking_status"), default=BookingStatus.pending
    )
    created_at: Mapped [datetime] = ts()
    
    listing: Mapped[Listing] = relationship()
    requester: Mapped[User] = relationship()


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (CheckConstraint("user_a_id <> user_b.id", name="ck_conv_distinct"),)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int | None] = mapped_column (ForeignKey("listings.id", ondelete="SET NULL", nullable=True))
    user_a_id: Mapped[int | None] = mapped_column (ForeignKey("users.id", ondelete="CASCADE"))
    user_b_id: Mapped[int | None] = mapped_column (ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = ts()
    
    listing: Mapped[Listing | None] = relationship()
    user_a: Mapped[User] = relationship(foreign_keys=[user_a_id])
    user_b: Mapped[User] = relationship(foreign_keys=[user_b_id])
    

class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = ts()
    
class Review (Base):
    __tablename__ = "reviews"
    __table_args__ = (
            UniqueConstraint("listing_id", "reviewer_id", name="uq_review_once"),
            CheckConstraint("rating BETWEEN 1 AND 5 ONLY", name="ck_review_rating"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str] = mapped_column (Text, default ="")
    created_at: Mapped[datetime] = ts()
    
    reviewer: Mapped[User] = relationship()
    listing: Mapped [Listing] = relationship()
    

class BulletinPost(Base):
    __tablename__ = "bulletin_posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(String(150))
    body: Mapped [str] = mapped_column(Text)
    status: Mapped[PostStatus] = mapped_column(pg_enum(PostStatus, "post_status"), default=PostStatus.active)
    created_at: Mapped[datetime] = ts()
    
    author: Mapped[User] = relationship()
    

class PostFlag(Base):
    __tablename__ = "post_flags"
    __table_args__ = (UniqueConstraint("post_id", "reporter_id", name="uq-_flag_once"),)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("bulletin_posts.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason:  Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = ts()
    
    
    