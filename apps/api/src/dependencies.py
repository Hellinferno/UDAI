from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict

from database import SessionLocal

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Validates token and extracts user identity/tenant.
    For Phase 1 MVP, we use a static verification just to get the security machinery in place.
    Any request with a Bearer token that isn't 'invalid' is accepted, returning a mock user.
    Production will replace this with python-jose JWT validation.
    """
    token = credentials.credentials
    if token == "invalid":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decoded mock user state
    return {
        "user_id": "usr_proto123",
        "tenant_id": "org_cyberbank",
        "role": "analyst"
    }

def get_db_and_user(
    db: Session = Depends(get_db),
    user: Dict = Depends(get_current_user)
):
    return {"db": db, "user": user}
