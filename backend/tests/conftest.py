from uuid import uuid4

import pytest

from app.api.main import app
from app.auth.dependencies import get_current_user
from app.db.models import User


@pytest.fixture
def authenticated_user():
    """为非认证专项测试提供模拟登录用户。"""

    user = User(
        id=uuid4(),
        email="planner-test@example.com",
        password_hash="not-used-in-this-test",
        display_name="测试用户",
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)
