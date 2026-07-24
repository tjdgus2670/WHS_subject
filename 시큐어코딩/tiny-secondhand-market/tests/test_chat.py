from tests.conftest import register_and_login, create_product


def _start_room(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/chat/start/1", follow_redirects=True)


def test_stranger_cannot_view_1to1_room(client):
    _start_room(client)
    client.get("/auth/logout")

    register_and_login(client, "stranger1", "제3자")
    resp = client.get("/chat/rooms/1")
    assert resp.status_code == 403


def test_stranger_cannot_send_message_to_room(client):
    _start_room(client)
    client.get("/auth/logout")

    register_and_login(client, "stranger1", "제3자")
    resp = client.post("/chat/rooms/1/messages", json={"content": "몰래 보내봄"})
    assert resp.status_code == 403


def test_stranger_cannot_poll_room(client):
    _start_room(client)
    client.get("/auth/logout")

    register_and_login(client, "stranger1", "제3자")
    resp = client.get("/chat/rooms/1/poll?after_id=0")
    assert resp.status_code == 403


def test_message_xss_payload_is_escaped_on_render(client):
    _start_room(client)
    client.post("/chat/rooms/1/messages", json={"content": "<script>alert(1)</script>"})

    resp = client.get("/chat/rooms/1")
    assert b"<script>alert(1)</script>" not in resp.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in resp.data


def test_blocked_user_cannot_start_chat(client, app):
    register_and_login(client, "seller1", "판매자1")
    create_product(client)

    from app.models.user import User
    with app.app_context():
        seller_id = User.query.filter_by(username="seller1").first().id

    client.get("/auth/logout")
    register_and_login(client, "buyer1", "구매자1")
    client.post(f"/users/{seller_id}/block")

    resp = client.post("/chat/start/1", follow_redirects=True)
    assert "차단 관계인 사용자와는 채팅을 시작할 수 없습니다".encode() in resp.data


def test_global_chat_hides_messages_from_blocked_user(client, app):
    register_and_login(client, "alice1", "앨리스")
    client.post("/chat/global/messages", json={"content": "안녕하세요 앨리스입니다"})

    from app.models.user import User
    with app.app_context():
        alice_id = User.query.filter_by(username="alice1").first().id

    client.get("/auth/logout")
    register_and_login(client, "bob1", "바비")
    client.post(f"/users/{alice_id}/block")

    resp = client.get("/chat/global")
    assert "안녕하세요 앨리스입니다".encode() not in resp.data


def test_first_five_rapid_room_messages_are_allowed_sixth_is_blocked(client):
    _start_room(client)
    # 마지막 로그인 상태는 buyer1. 5개까지는 연속으로 보내도 자유롭게 허용돼야 한다.
    for i in range(5):
        resp = client.post("/chat/rooms/1/messages", json={"content": f"메시지 {i+1}"})
        assert resp.status_code == 200

    sixth = client.post("/chat/rooms/1/messages", json={"content": "6번째 메시지"})
    assert sixth.status_code == 429
    # jsonify()는 기본적으로 ensure_ascii=True라서 한글이 \uXXXX로 이스케이프된 채 내려온다.
    # resp.data(원본 바이트)에서 한글을 직접 찾으면 실패하므로, 파싱된 JSON 값으로 비교한다.
    assert "너무 많이" in sixth.get_json()["error"]


def test_room_message_allowed_again_after_burst_window_passes(client, monkeypatch):
    import app.chat.routes as chat_routes
    monkeypatch.setattr(chat_routes, "MESSAGE_BURST_WINDOW_SECONDS", 0)  # 창을 0으로 좁혀 즉시 리셋되게 함

    _start_room(client)
    for i in range(5):
        resp = client.post("/chat/rooms/1/messages", json={"content": f"메시지 {i+1}"})
        assert resp.status_code == 200

    # 창이 0초라 방금 보낸 메시지들이 이미 "최근" 범위 밖이므로 바로 다시 보낼 수 있어야 한다.
    sixth = client.post("/chat/rooms/1/messages", json={"content": "창 지난 뒤 메시지"})
    assert sixth.status_code == 200


def test_first_five_rapid_global_messages_allowed_sixth_blocked(client):
    register_and_login(client, "globaluser1", "전체채팅유저")
    for i in range(5):
        resp = client.post("/chat/global/messages", json={"content": f"메시지 {i+1}"})
        assert resp.status_code == 200

    sixth = client.post("/chat/global/messages", json={"content": "6번째 메시지"})
    assert sixth.status_code == 429
