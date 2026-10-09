from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import User, UserRole
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut, UserUpdate
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

INSTITUTIONAL_ROLES = {"student", "faculty"}


def _is_institutional(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in settings.institutional_domains


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    
    if data.role in INSTITUTIONAL_ROLES and not _is_institutional(email):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Students and faculty must register with a CPUT email address (e.g. name@mycput.ac.za)",
        )
        
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
        
    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=hash_password(data.password),
        role=UserRole(data.role),
        is_verified=data.role in INSTITUTIONAL_ROLES,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
        
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
        
    return {
        "access_token": create_access_token(user.id, user.role.value), 
        "token_type": "bearer", 
        "user": user
    }


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name.strip()
    db.commit()
    db.refresh(user)
    return user