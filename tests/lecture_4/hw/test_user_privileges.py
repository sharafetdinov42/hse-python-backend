import pytest
from lecture_4.demo_service.core.users import UserService, UserInfo, UserRole, password_is_longer_than_8


def test_admin_privileges_granting():
    user_service = UserService()
    new_user_info = UserInfo(
        username="sampleuser",
        name="Sample User",
        birthdate="1990-01-01T00:00:00",
        password="SecurePassword456"
    )
    created_user = user_service.register(new_user_info)
    user_service.grant_admin(created_user.uid)
    assert user_service.get_by_id(created_user.uid).info.role == UserRole.ADMIN

def test_granting_admin_to_nonexistent_user():
    user_service = UserService()
    with pytest.raises(ValueError, match="user not found"):
        user_service.grant_admin(999)

def test_password_length_validation():
    assert password_is_longer_than_8("SecurePass") is True
    assert password_is_longer_than_8("short") is False
