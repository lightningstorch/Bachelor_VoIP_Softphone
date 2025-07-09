import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.hash import pbkdf2_sha256
from datetime import datetime, timedelta
from config.config import access_token_expire_minutes, secret_key, algorithm
from datastructure.database.database import get_user

#===================================
#        Password Functions
#===================================

def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2 with SHA-256.
    :param password: The password to hash.
    :return: The hashed password.
    """
    return pbkdf2_sha256.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a hashed password.
    :param plain_password: The plain password to verify.
    :param hashed_password: The hashed password from the Db.
    :return: Boolean indicating whether the password matches.
    """
    return pbkdf2_sha256.verify(plain_password, hashed_password)

#=================================================
#        Authentication and Token Functions
#=================================================

def create_token(username: str):
    """
    Creates a JWT token for the given username.
    :param username: The username for which to create the token.
    :return: The JWT token as a string.
    """
    expire_date = datetime.now() + timedelta(minutes=access_token_expire_minutes)
    data = {
        "sub": username,
        "exp": expire_date
    }
    return jwt.encode(data, key=secret_key, algorithm=algorithm)

def verify_token(token: str = Depends(OAuth2PasswordBearer(tokenUrl="/api/login"))):
    """
    Verifies the JWT token and returns the user if valid.
    :param token: The JWT token to verify.
    :return: The user object if the token is valid.
    """
    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, key=secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise exception
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

    db_user = get_user(username)
    if db_user is None:
        raise exception
    return db_user

def authenticate(username: str, password: str):
    """
    Authenticates a user by checking the username and password.
    This function retrieves the user from the database and verifies the password.
    :param username: The username of the user to authenticate.
    :param password: The password of the user to authenticate.
    :return: The user object if authentication is successful, None otherwise.
    """
    db_user = get_user(username)
    if not db_user:
        return None
    if not verify_password(password, db_user.password):
        return None
    return db_user



