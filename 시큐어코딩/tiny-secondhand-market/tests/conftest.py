import io
import pytest
from PIL import Image

from app import create_app
from app.extensions import db as _db
from config import Config


class BaseTestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False  # 대부분의 테스트는 CSRF를 끄고 비즈니스 로직/권한 로직에 집중한다
    SECRET_KEY = "test-secret-key"
    SESSION_COOKIE_SECURE = False


@pytest.fixture
def app(tmp_path):
    class _Config(BaseTestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path}/test.db"
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = create_app(_Config)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------- 공용 헬퍼 ----------------

def register(client, username, nickname="테스터", password="abcd1234", region="서울시"):
    return client.post("/auth/register", data={
        "username": username,
        "email": f"{username}@example.com",
        "nickname": nickname,
        "region": region,
        "password": password,
        "password_confirm": password,
    }, follow_redirects=True)


def login(client, username, password="abcd1234"):
    return client.post("/auth/login", data={
        "username": username, "password": password,
    }, follow_redirects=True)


def register_and_login(client, username, nickname="테스터"):
    register(client, username, nickname)
    return login(client, username)


def make_test_image_bytes(color="red", size=(20, 20), fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format=fmt)
    buf.seek(0)
    return buf


def create_product(client, title="테스트 상품", price=10000, description="테스트용 상품 설명입니다"):
    img = make_test_image_bytes()
    return client.post("/products/new", data={
        "title": title,
        "description": description,
        "price": str(price),
        "category": "etc",
        "condition": "used",
        "images": (img, "test.png"),
    }, content_type="multipart/form-data", follow_redirects=True)
