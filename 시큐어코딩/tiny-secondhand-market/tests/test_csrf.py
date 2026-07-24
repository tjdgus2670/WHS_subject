import pytest

from app import create_app
from app.extensions import db as _db
from config import Config
from tests.conftest import register, login, create_product


@pytest.fixture
def csrf_client(tmp_path):
    class _Config(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path}/test_csrf.db"
        WTF_CSRF_ENABLED = True  # 이 테스트에서만 CSRF 보호를 실제로 켠다
        SECRET_KEY = "test-secret-key"
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = create_app(_Config)
    with application.app_context():
        _db.create_all()
        yield application.test_client()
        _db.session.remove()
        _db.drop_all()


def test_register_without_csrf_token_rejected(csrf_client):
    resp = csrf_client.post("/auth/register", data={
        "username": "hacker1",
        "email": "hacker1@example.com",
        "nickname": "해커",
        "region": "서울시",
        "password": "abcd1234",
        "password_confirm": "abcd1234",
    })
    assert resp.status_code == 400


def test_register_with_valid_csrf_token_succeeds(csrf_client):
    # 폼 페이지에서 실제 토큰을 받아와서 사용해야 통과한다
    get_resp = csrf_client.get("/auth/register")
    html = get_resp.data.decode()
    start = html.find('name="csrf_token" type="hidden" value="') + len('name="csrf_token" type="hidden" value="')
    end = html.find('"', start)
    token = html[start:end]

    resp = csrf_client.post("/auth/register", data={
        "csrf_token": token,
        "username": "realuser1",
        "email": "realuser1@example.com",
        "nickname": "정상유저",
        "region": "서울시",
        "password": "abcd1234",
        "password_confirm": "abcd1234",
    }, follow_redirects=True)
    assert "회원가입이 완료되었습니다".encode() in resp.data


def _meta_csrf_token(client, path="/"):
    """base.html에 있는 <meta name="csrf-token" ...> 값을 읽어온다.
    로그인 라우트가 session.clear()로 세션을 재발급하므로, 로그인 전/후에 쓸 토큰은
    반드시 그 시점 이후에 새로 받아와야 한다."""
    resp = client.get(path)
    html = resp.data.decode()
    marker = 'name="csrf-token" content="'
    idx = html.find(marker)
    assert idx != -1, (
        f"{path} 응답에서 csrf-token 메타태그를 찾지 못함 "
        f"(status={resp.status_code}, body 앞부분={html[:200]!r})"
    )
    start = idx + len(marker)
    end = html.find('"', start)
    return html[start:end]


def _setup_chat_room_with_csrf_disabled(csrf_client, seller, buyer, product_title):
    """검증 대상이 아닌 준비 단계(회원가입/로그인/상품등록/채팅방 생성)는 CSRF를 잠깐 꺼서
    이미 다른 60여 개 테스트에서 검증된 conftest의 register/login/create_product를 그대로 쓴다.
    커스텀 HTML 스크래핑으로 이 단계를 짜다가 원인 불명의 리다이렉트로 계속 깨졌어서,
    검증된 헬퍼를 재사용하는 쪽이 훨씬 안정적이다."""
    csrf_client.application.config["WTF_CSRF_ENABLED"] = False
    try:
        register(csrf_client, seller, f"{seller}닉네임")
        login(csrf_client, seller)
        create_product(csrf_client, title=product_title)
        csrf_client.get("/auth/logout")

        register(csrf_client, buyer, f"{buyer}닉네임")
        login(csrf_client, buyer)
        csrf_client.post("/chat/start/1", follow_redirects=True)
    finally:
        csrf_client.application.config["WTF_CSRF_ENABLED"] = True


def test_chat_room_message_without_csrf_token_rejected(csrf_client):
    _setup_chat_room_with_csrf_disabled(csrf_client, "chatseller1", "chatbuyer1", "채팅용상품")

    # 여기서부터가 핵심: X-CSRFToken 헤더 없이 JSON으로 메시지 전송을 시도한다.
    resp = csrf_client.post("/chat/rooms/1/messages", json={"content": "안녕하세요"})
    assert resp.status_code == 400


def test_global_chat_message_without_csrf_token_rejected(csrf_client):
    csrf_client.application.config["WTF_CSRF_ENABLED"] = False
    try:
        register(csrf_client, "globaluser1", "전체채팅유저")
        login(csrf_client, "globaluser1")
    finally:
        csrf_client.application.config["WTF_CSRF_ENABLED"] = True

    resp = csrf_client.post("/chat/global/messages", json={"content": "전체채팅 테스트"})
    assert resp.status_code == 400
