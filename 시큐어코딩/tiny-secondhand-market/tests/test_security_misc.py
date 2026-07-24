from tests.conftest import register_and_login, create_product, register
from tests.test_reports_admin import _make_admin


# ---------------- 위시리스트 IDOR ----------------

def test_wishlist_toggle_only_affects_own_wish(client, app):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="위시상품")
    client.get("/auth/logout")

    register_and_login(client, "userA", "유저A")
    client.post("/products/1/wish")
    client.get("/auth/logout")

    register_and_login(client, "userB", "유저B")
    client.post("/products/1/wish")

    from app.models.wish import Wish
    from app.models.user import User
    with app.app_context():
        wishes = Wish.query.filter_by(product_id=1).all()
        assert len(wishes) == 2  # A, B 각자 자기 것만 생겼어야 함

    # B가 다시 요청(토글 해제)해도 A의 찜은 그대로 남아야 한다
    client.post("/products/1/wish")
    with app.app_context():
        remaining = Wish.query.filter_by(product_id=1).all()
        assert len(remaining) == 1
        user_a = User.query.filter_by(username="userA").first()
        assert remaining[0].user_id == user_a.id


# ---------------- 관리자 개별 라우트 ----------------

def test_non_admin_cannot_access_report_queue(client):
    register_and_login(client, "user1", "일반유저1")
    resp = client.get("/admin/reports")
    assert resp.status_code == 403


def test_non_admin_cannot_access_admin_logs(client):
    register_and_login(client, "user2", "일반유저2")
    resp = client.get("/admin/logs")
    assert resp.status_code == 403


def test_non_admin_cannot_dismiss_report(client):
    register_and_login(client, "user3", "일반유저3")
    resp = client.post("/admin/reports/1/dismiss")
    assert resp.status_code == 403


def test_admin_can_access_report_queue_and_logs(client, app):
    register_and_login(client, "adminuser3", "관리자3")
    _make_admin(app, "adminuser3")

    assert client.get("/admin/reports").status_code == 200
    assert client.get("/admin/logs").status_code == 200


# ---------------- 세션 재발급 / 쿠키 속성 ----------------

def test_login_regenerates_session_cookie(client):
    # base.html의 csrf_token() 호출로 세션에 값이 하나 생기므로, 로그인 전에도 쿠키가 발급된다.
    # ("/"는 상품 목록으로 리다이렉트만 하고 그 자체로는 세션에 아무것도 안 남기므로 직접 접근)
    resp_before = client.get("/products/")
    cookie_before = resp_before.headers.get("Set-Cookie")
    assert cookie_before is not None

    register(client, "sessuser1", "세션테스트")
    resp_login = client.post("/auth/login", data={
        "username": "sessuser1", "password": "abcd1234",
    })
    cookie_after = resp_login.headers.get("Set-Cookie")

    # 로그인 라우트가 session.clear() 이후 login_user()를 호출하므로
    # 세션 쿠키 값 자체가 로그인 전/후로 달라져야 한다 (세션 고정 공격 방지).
    assert cookie_after is not None
    assert cookie_after.split(";")[0] != cookie_before.split(";")[0]


def test_logout_invalidates_session_for_protected_page(client):
    register_and_login(client, "logoutuser1", "로그아웃테스트")
    assert client.get("/mypage/").status_code == 200

    client.get("/auth/logout")
    resp = client.get("/mypage/", follow_redirects=True)
    assert "로그인이 필요합니다".encode() in resp.data


def test_login_response_cookie_has_httponly_and_samesite(client):
    register(client, "cookieuser1", "쿠키테스트")
    resp = client.post("/auth/login", data={
        "username": "cookieuser1", "password": "abcd1234",
    })
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


GENERIC_LOGIN_ERROR = "아이디 또는 비밀번호가 올바르지 않습니다".encode()


def test_nonexistent_username_always_shows_generic_error(client):
    resp = None
    for _ in range(6):
        resp = client.post("/auth/login", data={
            "username": "no_such_user_ever", "password": "wrongpass",
        }, follow_redirects=True)
    assert GENERIC_LOGIN_ERROR in resp.data


def test_locked_real_account_shows_identical_generic_error(client):
    # 실제 계정을 잠금 임계치(5회)만큼 틀리게 로그인해서 잠근 뒤, 그 다음 시도의 응답 문구가
    # 존재하지 않는 계정의 응답 문구와 완전히 동일해야 한다. (예전에는 "로그인 시도가 많아
    # 일시적으로 잠겼습니다"라는 별도 문구가 있어서, 반복 시도로 계정 존재 여부를 추측할 수
    # 있는 사이드채널이었다 - 지금은 통일된 문구만 응답한다.)
    register(client, "locktarget1", "잠금대상유저")

    resp = None
    for _ in range(6):  # 5회 실패로 잠기고, 6번째 시도의 응답을 확인
        resp = client.post("/auth/login", data={
            "username": "locktarget1", "password": "wrongpass",
        }, follow_redirects=True)

    assert GENERIC_LOGIN_ERROR in resp.data
    assert "잠겼습니다".encode() not in resp.data
