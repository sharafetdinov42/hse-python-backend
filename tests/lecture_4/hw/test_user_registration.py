import pytest
from lecture_4.demo_service.core.users import UserService, UserInfo, UserRole


def test_user_creation():
    user_service = UserService()
    new_user_info = UserInfo(
        username="sampleuser",
        name="Sample User",
        birthdate="1990-01-01T00:00:00",
        password="SecurePassword456"
    )
    created_user = user_service.register(new_user_info)
    assert created_user.uid == 1
    assert created_user.info.username == "sampleuser"
    assert created_user.info.role == UserRole.USER

def test_duplicate_username_registration():
    user_service = UserService()
    new_user_info = UserInfo(
        username="sampleuser",
        name="Sample User",
        birthdate="1990-01-01T00:00:00",
        password="SecurePassword456"
    )
    user_service.register(new_user_info)
    with pytest.raises(ValueError, match="username is already taken"):
        user_service.register(new_user_info)

def test_nonexistent_user_lookup():
    user_service = UserService()
    assert user_service.get_by_username("unknownuser") is None
