import pytest
import time
import jwt

from config.config import secret_key, algorithm
from unittest.mock import patch, MagicMock
from datastructure.database.models import UiUser
from utils.auth import verify_token
from fastapi import HTTPException
from src.utils.auth import create_token
from utils.auth import hash_password, authenticate, verify_password

# ==================================================
#             Pytest Fixtures
# ==================================================

@pytest.fixture()
def data_test_user():
    username = "testuser"
    password = "testpassword"
    return username, password

#==================================================
#              Password Functions Tests
#==================================================

def test_hash_password():
    password = "testpassword"
    hashed = hash_password(password)
    assert isinstance(hashed, str)

    assert hashed != password

def test_hash_password_twice_same():
    password = "testpassword"
    hashed1 = hash_password(password)
    hashed2 = hash_password(password)

    assert hashed1 != hashed2

def test_verify_password():
    password = "testpassword"
    hashed = hash_password(password)

    assert verify_password(password, hashed)

    assert not verify_password("wrongpassword", hashed)

#==================================================
#     Authentication and Token Functions Tests
#==================================================

def test_create_token(data_test_user):
    username, _ = data_test_user
    token = create_token(username)

    assert isinstance(token, str)
    assert len(token) > 0

def test_verify_token_directly(data_test_user):
    username, password = data_test_user

    token = create_token(username)

    with patch("utils.auth.get_user") as mock_get_user:
        mock_user = MagicMock()
        mock_user.username = username
        mock_get_user.return_value = mock_user

        from utils.auth import verify_token
        result = verify_token(token)

        assert result == mock_user
        assert result.username == username
        mock_get_user.assert_called_once_with(username)

def test_verify_token_expired():
    username = "testuser"

    # create a token that has expired
    expired_time = int(time.time()) - 300
    payload = {"sub": username, "exp": expired_time}
    expired_token = jwt.encode(payload, key=secret_key, algorithm=algorithm)

    with pytest.raises(ValueError, match="Token has expired"):
        verify_token(expired_token)

def test_verify_token_invalid():
    invalid_token = "invalid.token.string"

    with pytest.raises(ValueError, match="Invalid token"):
        verify_token(invalid_token)

def test_verify_token_user_not_found():
    username = "nonexistent"
    token = create_token(username)

    with patch("utils.auth.get_user", return_value=None):

        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

def test_authentication_success(data_test_user):
    username, password = data_test_user

    with patch("utils.auth.get_user") as mock_get_user:
        mock_user = UiUser(username=username, password=hash_password(password))
        mock_get_user.return_value = mock_user

        user = authenticate(username=username, password=password)
        assert user is not None
        assert user.username == username
        assert verify_password(password, user.password)

def test_authentication_failure(data_test_user):
    username, password = data_test_user

    with patch("utils.auth.get_user") as mock_get_user:
        mock_user = UiUser(username=username, password=hash_password(password))
        mock_get_user.return_value = mock_user

        user = authenticate(username=username, password="wrongpassword")
        assert user is None

        user = authenticate(username="nonexistent", password="any")
        assert user is None
