from tests.conftest import register, register_and_login, create_product


def _make_admin(app, username):
    from app.models.user import User, UserRole
    from app.extensions import db

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        user.role = UserRole.ADMIN
        db.session.commit()


def test_product_auto_blocked_after_report_threshold(client, app):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="의심상품")
    client.get("/auth/logout")

    threshold = app.config["PRODUCT_REPORT_BLOCK_THRESHOLD"]
    for i in range(threshold):
        register_and_login(client, f"reporter{i}", f"신고자{i}")
        client.post("/reports/product/1", data={"reason": "fraud", "description": f"신고{i}"})
        client.get("/auth/logout")

    from app.models.product import Product, ProductStatus
    with app.app_context():
        p = Product.query.get(1)
        assert p.status == ProductStatus.BLOCKED


def test_duplicate_report_is_prevented(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="상품A")
    client.get("/auth/logout")

    register_and_login(client, "reporter1", "신고자1")
    client.post("/reports/product/1", data={"reason": "fraud", "description": "첫신고"})

    resp = client.post("/reports/product/1", data={"reason": "fraud", "description": "또신고"}, follow_redirects=True)
    assert "이미 신고한 상품입니다".encode() in resp.data


def test_user_becomes_dormant_after_report_threshold_and_login_blocked(client, app):
    register(client, "victim1", "피해자")

    from app.models.user import User
    with app.app_context():
        victim_id = User.query.filter_by(username="victim1").first().id

    threshold = app.config["USER_REPORT_DORMANT_THRESHOLD"]
    for i in range(threshold):
        register_and_login(client, f"rep{i}", f"레포터{i}")
        client.post(f"/reports/user/{victim_id}", data={"reason": "abusive", "description": f"신고{i}"})
        client.get("/auth/logout")

    resp = client.post("/auth/login", data={
        "username": "victim1", "password": "abcd1234",
    }, follow_redirects=True)
    assert "아이디 또는 비밀번호가 올바르지 않습니다".encode() in resp.data


def test_dormant_user_with_active_session_cannot_create_product(client, app):
    register_and_login(client, "victim2", "피해자2")

    from app.models.user import User, UserStatus
    from app.extensions import db
    with app.app_context():
        victim = User.query.filter_by(username="victim2").first()
        victim.status = UserStatus.DORMANT
        db.session.commit()

    # 로그인 세션은 아직 살아있는 상태 (로그아웃 안 함)에서 글쓰기 시도
    resp = client.get("/products/new", follow_redirects=True)
    assert "휴면 또는 정지된 계정".encode() in resp.data


def test_non_admin_cannot_access_admin_dashboard(client):
    register_and_login(client, "normal1", "평범이")
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_admin_can_access_dashboard(client, app):
    register_and_login(client, "adminuser1", "관리자1")
    _make_admin(app, "adminuser1")
    resp = client.get("/admin/")
    assert resp.status_code == 200


def test_admin_manual_block_marks_report_reviewed(client, app):
    register_and_login(client, "seller2", "판매자2")
    create_product(client, title="관리자테스트상품")
    client.get("/auth/logout")

    register_and_login(client, "reporter9", "신고자9")
    client.post("/reports/product/1", data={"reason": "etc", "description": "신고"})
    client.get("/auth/logout")

    register_and_login(client, "adminuser2", "관리자2")
    _make_admin(app, "adminuser2")

    resp = client.post("/admin/products/1/block", follow_redirects=True)
    assert resp.status_code == 200

    from app.models.product import Product, ProductStatus
    from app.models.report import Report, ReportStatus
    with app.app_context():
        assert Product.query.get(1).status == ProductStatus.BLOCKED
        report = Report.query.filter_by(target_id=1).first()
        assert report.status == ReportStatus.REVIEWED
