import pytest
from fastapi import FastAPI, HTTPException
from lecture_4.demo_service.api.utils import requires_admin
from lecture_4.demo_service.core.users import UserService, UserInfo, UserRole
from datetime import datetime
from starlette.requests import Request
from http import HTTPStatus
from lecture_4.demo_service.api.utils import (
    initialize,
    user_service,
)


@pytest.fixture
def app_setup():
    application = FastAPI()
    application.state.user_service = UserService(password_validators=[])
    return application

@pytest.fixture
async def setup_service(app_setup: FastAPI):
    async with initialize(app_setup):
        yield

def test_admin_access(app_setup):
    req = Request(scope={"type": "http", "app": app_setup})
    service = user_service(req)
    admin_info = UserInfo(
        username="admin_user",
        name="Administrator",
        birthdate=datetime(1985, 1, 1),
        role=UserRole.ADMIN,
        password="AdminPass123",
    )
    admin_entity = service.register(admin_info)

    admin = requires_admin(admin_entity)
    assert admin.info.username == "admin_user"

def test_admin_access_forbidden_regular_user(app_setup):
    req = Request(scope={"type": "http", "app": app_setup})
    service = user_service(req)
    
    user_info = UserInfo(
        username="regular_user",
        name="Regular Joe",
        birthdate=datetime(1992, 2, 2),
        role=UserRole.USER,
        password="UserPass123",
    )
    user_entity = service.register(user_info)
    
    with pytest.raises(HTTPException) as exc_info:
        requires_admin(user_entity)
    assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
