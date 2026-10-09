#Shared FastAPI dependencies for the backend
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserRole
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def user_from_credentials(creds: HTTPAuthorizationCredentials | None, db: Session)  -> User | None:
    if creds is None:
        return None
    payload = decode_access_token(creds.credentials)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user

def get_current_user_optional (
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db)   
) -> User | None:
    return _user_from_credentials(creds, db)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db)
) -> User:
    user = _user_from_credentials(creds,db)
    if user is None:
        raise HTTPException (
            status.HTTP_401_UNAUTHORIZED,
            "Not Authenticated or session expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required.")
    return user