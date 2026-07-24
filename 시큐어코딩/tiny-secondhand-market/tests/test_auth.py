from tests.conftest import register, login, register_and_login


def test_register_and_login_success(client):
    register(client, "alice1", "앨리스")
    resp = login(client, "alice1")
    assert resp.status_code == 200
    assert "앨리스".encode() in resp.data


def test_duplicate_registration_shows_generic_message(client):
    register(client, "alice1", "앨리스")
    resp = register(client, "alice1", "다른닉네임")
    # 아이디 중복인지 이메일 중복인지 구분해서 알려주지 않는다 (계정 열거 방지)
    assert "이미 사용 중인 아이디 또는 이메일입니다".encode() in resp.data


def test_wrong_password_gives_generic_error(client):
    register(client, "alice1", "앨리스")
    resp = client.post("/auth/login", data={
        "username": "alice1", "password": "wrongpassword",
    }, follow_redirects=True)
    assert "아이디 또는 비밀번호가 올바르지 않습니다".encode() in resp.data


def test_nonexistent_user_gives_same_generic_error(client):
    # 존재하지 않는 아이디도, 비밀번호가 틀린 것도 동일한 메시지여야 계정 존재 여부를 못 알아낸다
    resp = client.post("/auth/login", data={
        "username": "ghost_user", "password": "whatever123",
    }, follow_redirects=True)
    assert "아이디 또는 비밀번호가 올바르지 않습니다".encode() in resp.data


def test_login_locks_after_max_attempts(client, app):
    register(client, "bob1", "바비")
    max_attempts = app.config["MAX_LOGIN_ATTEMPTS"]

    for _ in range(max_attempts):
        client.post("/auth/login", data={"username": "bob1", "password": "wrongpass"})

    resp = client.post("/auth/login", data={
        "username": "bob1", "password": "wrongpass",
    }, follow_redirects=True)
    # 잠금 메시지는 계정 열거(user enumeration) 방지를 위해 일반 오류 메시지와 통일했다
    # (다른 문구였다면 반복 시도만으로 "이 아이디는 실제로 존재한다"를 추측할 수 있었음).
    assert "아이디 또는 비밀번호가 올바르지 않습니다".encode() in resp.data

    from app.models.user import User
    with app.app_context():
        user = User.query.filter_by(username="bob1").first()
        assert user.is_locked()  # 문구는 같아도 실제로는 잠긴 상태여야 한다


def test_password_change_requires_current_password(client):
    register_and_login(client, "carol1", "캐롤")
    resp = client.post("/auth/password", data={
        "current_password": "wrongcurrent1",
        "new_password": "newpass1234",
        "new_password_confirm": "newpass1234",
    }, follow_redirects=True)
    assert "현재 비밀번호가 올바르지 않습니다".encode() in resp.data


def test_password_is_hashed_not_stored_plaintext(client, app):
    from app.models.user import User

    register(client, "dave1", "데이브")
    with app.app_context():
        user = User.query.filter_by(username="dave1").first()
        assert user.password_hash != "abcd1234"
        assert user.password_hash.startswith("$2")  # bcrypt 해시 형식


def test_mypage_requires_login(client):
    resp = client.get("/mypage/", follow_redirects=True)
    assert "로그인이 필요합니다".encode() in resp.data
