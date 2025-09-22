from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db)
) -> schemas.CurrentUser:
    """
    Verify Firebase ID token and get essential user information.
    Falls back to X-User-ID header if bearer token is not provided.
    
    Args:
        credentials: The HTTP Authorization credentials.
        x_user_id: Optional X-User-ID header value.
        db: The database session.
        
    Returns:
        CurrentUser: Simplified user object with id, email, display_name, username, and credits
        
    Raises:
        HTTPException: If both token and X-User-ID are invalid or missing
    """
    if credentials is None and x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Either Bearer authentication or X-User-ID header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        if credentials:
            # Verify Firebase ID token
            try:
                decoded_token = auth.verify_id_token(credentials.credentials)
                
                # Extract user information from Firebase token
                user_id = decoded_token.get("uid")
                email = decoded_token.get("email")
                display_name = decoded_token.get("name")
                
                # Check if user exists in our database
                db_user = crud.get_user(db, user_id)
                
                if db_user:
                    # Update only display_name for existing user if we have it from token
                    if display_name:
                        db_user = crud.update_user_display_name(db, user_id, display_name)
                else:
                    # Create new user with Firebase info (no password needed for Firebase users)
                    db_user = crud.create_user(db, user_id, email, display_name or "", state="active")
                
                email = db_user.email
                display_name = db_user.display_name
                username = db_user.username
                credits = db_user.credits
                
            except Exception as firebase_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {str(firebase_error)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # Use X-User-ID header
            user_id = x_user_id
            # Get user info from database
            db_user = crud.get_user(db, user_id)
            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid X-User-ID",
                )
            email = db_user.email
            display_name = db_user.display_name
            username = db_user.username
            credits = db_user.credits
        
        # Return simplified user object with just the essential info
        return schemas.CurrentUser(
            id=user_id,
            email=email,
            display_name=display_name,
            username=username,
            pronouns=getattr(db_user, 'pronouns', None),
            credits=credits
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) 