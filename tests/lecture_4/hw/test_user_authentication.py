import pytest
from fastapi import FastAPI, HTTPException
from lecture_4.demo_service.api.utils import (
    initialize,
    user_service,
    requires_author,
)
from lecture_4.demo_service.core.users import UserService, UserInfo, UserRole
from fastapi.security import HTTPBasicCredentials
from datetime import datetime
from starlette.requests import Request
from http import HTTPStatus


@pytest.fixture
def test_app():
    application = FastAPI()
    application.state.user_service = UserService(password_validators=[])
    return application

@pytest.fixture
async def user_service_setup(test_app: FastAPI):
    async with initialize(test_app):
        yield

def test_authentication_service(test_app):
    req = Request(scope={"type": "http", "app": test_app})
    service = user_service(req)
    assert isinstance(service, UserService)

def test_authorization_success(test_app):
    req = Request(scope={"type": "http", "app": test_app})
    service = user_service(req)
    
    service.register(UserInfo(
        username="test_user",
        name="Test User",
        birthdate=datetime(1995, 5, 5),
        role=UserRole.USER,
        password="SecurePass123",
    ))
    
    credentials = HTTPBasicCredentials(username="test_user", password="SecurePass123")
    user_entity = requires_author(credentials, service)
    assert user_entity.info.username == "test_user"

def test_authorization_failure_invalid_password(test_app):
    req = Request(scope={"type": "http", "app": test_app})
    service = user_service(req)
    service.register(UserInfo(
        username="test_user",
        name="Test User",
        birthdate=datetime(1995, 5, 5),
        role=UserRole.USER,
        password="SecurePass123",
    ))
    
    credentials = HTTPBasicCredentials(username="test_user", password="WrongPassword")
    with pytest.raises(HTTPException) as exc_info:
        requires_author(credentials, service)
    assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED

def test_authorization_failure_nonexistent_user(test_app):
    req = Request(scope={"type": "http", "app": test_app})
    service = user_service(req)
    
    credentials = HTTPBasicCredentials(username="ghost_user", password="AnyPassword")
    with pytest.raises(HTTPException) as exc_info:
        requires_author(credentials, service)
    assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED
