"""Pydantic models"""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ----------------- USER AUTH ---------------------
SelfServiceRole = Literal["student", "Faculty", "Vendor", "Resident"]


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: SelfServiceRole = "student"
    
    @field_validator("full_name")
    @classmethod
    def _strip(cls, v:str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name is required")
        return v


class LoginIn(BaseModel):
    email:EmailStr
    password: str = Field(min_length=1, max_length=128)
    

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    role: str
    is_verified: bool
    created_at: datetime
    
    @field_validator("role", mode="before")
    @classmethod
    def _role_value(cls, v):
        return getattr(v, "value", v)

class UserBrief(BaseModel):
    id: int
    full_name: str
    role: str
    is_verified: bool = False
    

class UserUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    
# --------Reference Data----------
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    icon: str
    
    
class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field (default="", max_length=3000)
    price: float = Field(ge=0, le=10_000_000)
    price_unit: str = Field(default="", max_length=20)
    condition: str = Field(default="", max_length=30)
    icon: str = Field(default="", max_length=8)
    type: Literal["Product", "Service"] = "Product"
    category_id: int
    location_id: int | None = None
    


class ListingUpdate(BaseModel):
    title: str | None = Field (default=None, min_length=3, max_length=150)
    description: str | None = Field (default=None, max_length=3000)
    price: float | None = Field(default=None, ge=0, le=10_000_000)
    price_unit: str | None = Field(default=None, max_length=20)
    condition: str  | None = Field(default=None, max_length=30)
    icon: str | None = Field(default=None, max_length=8)
    category_id: int | None=None
    location_id: int | None = None
    status: Literal["active", "sold", "hidden"] | None = None
    

class ListingOut (BaseModel):
    id : int
    title: str
    description: str
    price: float
    price_unit: str
    condition: str
    icon: str
    type: str
    status: str
    category: CategoryOut
    location: LocationOut | None
    owner: UserBrief
    avg_rating: float
    review_count: int
    is_saved: bool = False
    created_at: datetime
    
class ListingPage(BaseModel):
    items: list[ListingOut]
    total: int
    page: int
    page_size: int
    

# ---------- BOOKINGS -----------
class BookingCreate(BaseModel):
    listing_id: int
    preferred_date: date | None = None
    preferred_time: time | None  = None
    notes: str = Field(default="", max_length=1000)
    
class BookingStatusIn(BaseModel):
    status: Literal["accepted", "declined", "cancelled", "completed"]
    
class ListingBrief(BaseModel):
    id: int
    title: str
    icon: str
    
class BookingOut(BaseModel):
    id: int
    listing: ListingBrief
    requester: UserBrief
    provider: UserBrief
    preffered_date:date | None
    preffered_time: time | None
    notes: str
    status: str
    created_at: datetime
    
    
# --------- MESSAGING ------------
class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    
    @field_validator("body")
    @classmethod
    def _not_blank(cls, v: str) -> str :
        if not v.strip():
            raise ValueError("Message cannot be blank")
        return v.strip()
    

class ConversationStart(MessageIn):
    listing_id: int | None = None
    recipient_id: int | None = None
    
class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    body: str
    is_read: bool
    created_at: datetime


class ConversationOut(BaseModel):
    id: int
    listing_id: str | None
    listing_title: str | None
    other_user: UserBrief
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int


# ---------- REVIEWS ---------
class ReviewOut(BaseModel):
    id: int
    listing_id: int
    listing_title: str
    rating: int
    comment: str
    reviewer: UserBrief
    created_at: datetime
    
class ReviewsOut(BaseModel):
    average: float
    count: int
    items: list[ReviewOut]
    

# ------- BULLETIN ---------
class PostOut(BaseModel):
    id: int
    title: str
    body: str
    status: str
    author: UserBrief
    flag_count: int
    is_mine: bool
    created_at: datetime
    

# ------ A D M I N ---------
class StatsOut(BaseModel):
    users: int
    unverified_users: int
    listings: int
    bookings: int
    messages: int
    reviews: int
    posts: int
    flagged_posts: int


    