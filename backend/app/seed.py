"""Data and demo data"""
from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import (
    Booking, BookingStatus, BulletinPost, Category, Conversation,
    Listing, ListingType, Location, Message, Review, User, UserRole,
)
from .security import hash_password

CATEGORIES = [("Textbooks"), ("Electronics"), ("Tutoring"), ("Services")]
LOCATIONS = ["Bellville Campus", "District Six Campus", "Mowbray Campus", "Granger Bay Campus", "Wellington Campus"]
DEMO_PASSWORD = "Password123!"

def seed_reference_data(db: Session) -> None:
    for name, icon in CATEGORIES:
        if not db.scalar(select(Category.id).where(Category.name == name)):
            db.add(Category(name=name, icon=icon))
    for name in LOCATIONS:
        if not db.scalar(select(Location.id).where(Location.name == name)):
            db.add(Location(name=name))
    db.commit()


def ensure_admin(db: Session) -> None:
    if (db.scalar(select(func.count(User.id))) or 0) > 1:
        return
    pw = hash_password(DEMO_PASSWORD)
    
    def user(name, email, role,verified=True):
        u = User(full_name=name, email=email, password_hash=pw, role=role, is_verified=verified)
        db.add(u)
        return u
    
    sipho = user ("Sipho Mokwena", "thandi@mycput.ac.za.", UserRole.student)
    thandi = user ("T-Books", "anjelonelson1@gmail.com", UserRole.resident)
    db.flush()
    
    cat = {c.name: c.id for c in db.scalars(select(Category))}
    loc = {l.name: l.id for l in db.scalars(select(Location))}
    
    laptop = Listing(owner_id=sipho.id, category_id=cat["Electronics"], location_id=loc["Bellville Campus"],
                     title="Student Laptop", price= 4500, condition="Great", 
                     description="Reliable laptop suitable for university assignments"),
    
    java = Listing(owner_id=thandi.id, category_id=cat["Textbooks"], location_id=loc["D6 Campus"],
                     title="Java Textbook", price= 4500, condition="Great", 
                     description="Java: How to Program latest edition")
    db.add_all([laptop, java])
    db.flush()
    
    for listing, reviewer, rating, text in [
        (laptop, sipho, 4, "Great device to use for heavy stuff"),
        (laptop, sipho, 5, "very fast, passed all my tests"),
        (java, thandi, 5, "Explained Java very well and properly for me as a beginner"),
    ]:
        db.add(Review(listing_id=listing.id, reviewer_id=reviewer.id, rating=rating, comment=text))
    
    
    a, b = sorted((sipho.id, thandi.id))
    conv = Conversation(user_a_id=a, user_b_id=b, listing_id=None)
    db.add(conv)
    db.flush()
    db.add_all ([
        Message(conversation_id=conv.id, sender_id=thandi.id, body="Hi! Is the laptop still available?"),
        Message(conversation_id=conv.id, sender_id=sipho.id, body="Yes, it is still available, come view it.")
    ])
    
    db.commit()