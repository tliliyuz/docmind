"""pytest 配置与共享 fixtures"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.core.security import create_access_token
from app.core.database import async_session


@pytest.fixture(scope="session", autouse=True)
def mock_chroma_init():
    """全局 Mock ChromaDB 初始化，避免测试时依赖 ChromaDB 环境"""
    with patch("app.core.chroma_client.init_chroma"):
        yield


@pytest.fixture
def mock_db():
    """Mock 异步 DB session — 各测试用例可自定义其返回值"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
async def async_client(mock_db):
    """带 mock DB 的 async HTTP 客户端，自动覆盖 get_db 依赖"""
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """生成有效 JWT 认证 header（普通用户 testuser）"""
    token = create_access_token(1, "testuser", "user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers():
    """生成有效 JWT 认证 header（管理员 admin）"""
    token = create_access_token(2, "admin", "admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user_auth_headers():
    """生成其他用户的 JWT 认证 header"""
    token = create_access_token(3, "otheruser", "user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def db_session():
    """真实数据库 session — 连接开发库，测试结束后自动关闭（未提交数据由 DB 回滚）"""
    async with async_session() as session:
        yield session
