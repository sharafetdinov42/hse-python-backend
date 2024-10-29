import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from lecture_4.demo_service.api.main import create_app
from lecture_4.demo_service.api.utils import initialize, requires_author
from lecture_4.demo_service.core.users import UserInfo, UserRole


@pytest_asyncio.fixture
async def app_fixture():
    app = create_app()
    app.dependency_overrides[requires_author] = lambda: None
    async with initialize(app):
        yield app

@pytest_asyncio.fixture
async def client_fixture(app_fixture):
    transport = ASGITransport(app=app_fixture, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

async def register_user(client, user_data):
    return await client.post("/user-register", json=user_data)

@pytest.mark.asyncio
async def test_admin_can_access_user(client_fixture, app_fixture):
    admin_data = {
        "username": "admin_user99",
        "name": "Admin User",
        "birthdate": "1980-01-01T00:00:00",
        "role": UserRole.ADMIN,
        "password": "AdminPassword123"
    }
    app_fixture.state.user_service.register(UserInfo(**admin_data))

    user_data = {
        "username": "testuser99",
        "name": "Test User",
        "birthdate": "1990-01-01T00:00:00",
        "password": "TestPassword123"
    }
    app_fixture.state.user_service.register(UserInfo(**user_data))

    admin_user = app_fixture.state.user_service.get_by_username("admin_user99")
    app_fixture.dependency_overrides[requires_author] = lambda: admin_user

    response = await client_fixture.post("/user-get?username=testuser99")
    assert response.status_code == 200
    assert response.json()["username"] == "testuser99"

    del app_fixture.dependency_overrides[requires_author]

@pytest.mark.asyncio
async def test_invalid_credentials_registration(client_fixture):
    user_data = {
        "username": "newuser",
        "name": "New User",
        "birthdate": "1995-05-05T00:00:00",
        "password": "short"
    }
    response = await register_user(client_fixture, user_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid password"

@pytest.mark.asyncio
async def test_user_registration(client_fixture):
    user_data = {
        "username": "testuser",
        "name": "Test User",
        "birthdate": "2000-01-01T00:00:00",
        "password": "validPassword123"
    }
    response = await register_user(client_fixture, user_data)
    assert response.status_code == 200
    assert response.json()["username"] == user_data["username"]

@pytest.mark.asyncio
async def test_duplicate_username_registration(client_fixture):
    user_data = {
        "username": "testuser",
        "name": "Test User",
        "birthdate": "2000-01-01T00:00:00",
        "password": "validPassword123"
    }
    await register_user(client_fixture, user_data)

    new_user_data = {
        "username": "testuser",
        "name": "Another User",
        "birthdate": "1990-01-01T00:00:00",
        "password": "validPassword123"
    }
    response = await register_user(client_fixture, new_user_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "username is already taken"

async def fetch_user_by_id(client, app, user_id):
    app.dependency_overrides[requires_author] = lambda: app.state.user_service.get_by_id(user_id)
    response = await client.post(f"/user-get?id={user_id}")
    del app.dependency_overrides[requires_author]
    return response

@pytest.mark.asyncio
async def test_retrieve_user_by_id(client_fixture, app_fixture):
    user_data = {
        "username": "testuser123",
        "name": "Test User",
        "birthdate": "1992-03-04T00:00:00",
        "password": "Password123"
    }
    response = await register_user(client_fixture, user_data)
    assert response.status_code == 200
    user_id = response.json()["uid"]

    response = await fetch_user_by_id(client_fixture, app_fixture, user_id)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_retrieve_user_by_username(client_fixture, app_fixture):
    user_data = {
        "username": "anotheruser",
        "name": "Another User",
        "birthdate": "1995-05-05T00:00:00",
        "password": "validPassword123"
    }
    response = await register_user(client_fixture, user_data)
    assert response.status_code == 200

    app_fixture.dependency_overrides[requires_author] = lambda: app_fixture.state.user_service.get_by_username("anotheruser")
    response = await client_fixture.post("/user-get?username=anotheruser")
    assert response.status_code == 200
    assert response.json()["username"] == "anotheruser"

    del app_fixture.dependency_overrides[requires_author]

@pytest.mark.asyncio
async def test_non_existent_user_access(client_fixture, app_fixture):
    admin_user = app_fixture.state.user_service.register(UserInfo(
        username="admin_test",
        name="Admin User",
        birthdate="1980-01-01T00:00:00",
        role=UserRole.ADMIN,
        password="AdminPassword123"
    ))

    app_fixture.dependency_overrides[requires_author] = lambda: admin_user

    response = await client_fixture.post("/user-get?username=non_existent_user")
    assert response.status_code == 404

    del app_fixture.dependency_overrides[requires_author]

@pytest.mark.asyncio
async def test_invalid_user_request_with_both_params(client_fixture, app_fixture):
    app_fixture.dependency_overrides[requires_author] = lambda: None

    response = await client_fixture.post("/user-get?id=1&username=testuser")
    assert response.status_code == 400

    del app_fixture.dependency_overrides[requires_author]

@pytest.mark.asyncio
async def test_invalid_user_request_without_params(client_fixture, app_fixture):
    app_fixture.dependency_overrides[requires_author] = lambda: None

    response = await client_fixture.post("/user-get")
    assert response.status_code == 400

    del app_fixture.dependency_overrides[requires_author]

@pytest.mark.asyncio
async def test_promote_user_functionality(client_fixture, app_fixture):
    admin_user = app_fixture.state.user_service.register(UserInfo(
        username="adminuser",
        name="Admin User",
        birthdate="1990-01-01T00:00:00",
        role=UserRole.ADMIN,
        password="AdminPassword123"
    ))

    user = app_fixture.state.user_service.register(UserInfo(
        username="user1",
        name="User One",
        birthdate="1995-05-05T00:00:00",
        role=UserRole.USER,
        password="UserPassword123"
    ))

    app_fixture.dependency_overrides[requires_author] = lambda: admin_user

    response = await client_fixture.post(f"/user-promote?id={user.uid}")
    assert response.status_code == 200

    promoted_user = app_fixture.state.user_service.get_by_id(user.uid)
    assert promoted_user is not None
    assert promoted_user.info.role == "admin"

    del app_fixture.dependency_overrides[requires_author]

@pytest.mark.asyncio
async def test_admin_not_found_on_promote(client_fixture):
    response = await client_fixture.put("/user-promote/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"

@pytest.mark.asyncio
async def test_direct_admin_granting(app_fixture):
    user_service = app_fixture.state.user_service
    user_data = {
        "username": "normaluser",
        "name": "Normal User",
        "birthdate": "1995-05-05T00:00:00",
        "password": "UserPassword123"
    }
    user = user_service.register(UserInfo(**user_data))

    user_service.grant_admin(user.uid)

    promoted_user = user_service.get_by_id(user.uid)
    assert promoted_user is not None
    assert promoted_user.info.role == "admin"

@pytest.mark.asyncio
async def test_coverage_of_user_api(client_fixture, app_fixture):
    admin_user = app_fixture.state.user_service.register(UserInfo(
        username="admin_user",
        name="Admin User",
        birthdate="1980-01-01T00:00:00",
        role=UserRole.ADMIN,
        password="AdminPassword123"
    ))

    user1 = app_fixture.state.user_service.register(UserInfo(
        username="user1",
        name="User One",
        birthdate="1990-01-01T00:00:00",
        role=UserRole.USER,
        password="UserPassword123"
    ))

    user2 = app_fixture.state.user_service.register(UserInfo(
        username="user2",
        name="User Two",
        birthdate="1992-02-02T00:00:00",
        role=UserRole.USER,
        password="UserPassword456"
    ))

    app_fixture.dependency_overrides[requires_author] = lambda: admin_user

    response = await client_fixture.post(f"/user-get?id={user1.uid}&username={user1.info.username}")
    assert response.status_code == 400

    response = await client_fixture.post("/user-get")
    assert response.status_code == 400

    response = await client_fixture.post(f"/user-get?id={user1.uid}")
    assert response.status_code == 200
    assert response.json()["username"] == "user1"

    response = await client_fixture.post(f"/user-get?username={user2.info.username}")
    assert response.status_code == 200
    assert response.json()["username"] == "user2"

    del app_fixture.dependency_overrides[requires_author]
    app_fixture.dependency_overrides[requires_author] = lambda: user1

    response = await client_fixture.post(f"/user-get?id={user1.uid}")
    assert response.status_code == 200
    assert response.json()["username"] == "user1"

    response = await client_fixture.post(f"/user-get?username={user1.info.username}")
    assert response.status_code == 200
    assert response.json()["username"] == "user1"

    response = await client_fixture.post(f"/user-get?id={user2.uid}")
    assert response.status_code == 500

    response = await client_fixture.post(f"/user-get?username={user2.info.username}")
    assert response.status_code == 500

    del app_fixture.dependency_overrides[requires_author]
    app_fixture.dependency_overrides[requires_author] = lambda: admin_user

    response = await client_fixture.post("/user-get?username=nonexistent_user")
    assert response.status_code == 404

    response = await client_fixture.post("/user-get?id=9999")
    assert response.status_code == 404

    del app_fixture.dependency_overrides[requires_author]
