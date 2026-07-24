from tests.conftest import register_and_login, create_product


def _setup_paid_transaction(client, price=50000, card="4242424242424242"):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, price=price)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/transactions/start/1", follow_redirects=True)
    client.post("/transactions/1/pay", data={
        "card_number": card, "expiry": "12/28", "cvc": "123",
    }, follow_redirects=True)


def test_payment_declined_for_card_ending_in_0000(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, price=10000)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/transactions/start/1", follow_redirects=True)

    resp = client.post("/transactions/1/pay", data={
        "card_number": "1234123412340000", "expiry": "12/28", "cvc": "123",
    }, follow_redirects=True)
    assert "거절되었습니다".encode() in resp.data

    from app.models.transaction import Transaction, TransactionStatus
    with client.application.app_context():
        tx = Transaction.query.get(1)
        assert tx.status == TransactionStatus.PENDING  # 거절됐으니 상태가 그대로여야 함


def test_free_giveaway_skips_card_payment_and_reserves_product(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, price=0)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    resp = client.post("/transactions/start/1", follow_redirects=True)
    assert "무료나눔 거래가 시작되었습니다".encode() in resp.data
    assert "무료나눔 (결제 없음)".encode() in resp.data

    from app.models.product import Product, ProductStatus
    from app.models.transaction import Transaction, TransactionStatus
    with client.application.app_context():
        assert Transaction.query.get(1).status == TransactionStatus.PAID
        assert Product.query.get(1).status == ProductStatus.RESERVED


def test_amount_cannot_be_tampered_by_client(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, price=77777)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    # 공격 시도: 클라이언트가 금액을 100원으로 조작해서 거래 시작을 요청
    client.post("/transactions/start/1", data={"amount": "100"}, follow_redirects=True)

    from app.models.transaction import Transaction
    with client.application.app_context():
        tx = Transaction.query.get(1)
        assert tx.amount == 77777  # 서버가 상품 가격 기준으로 결정하므로 조작이 반영되지 않는다


def test_stranger_cannot_view_transaction(client):
    _setup_paid_transaction(client)
    client.get("/auth/logout")

    register_and_login(client, "stranger1", "제3자")
    resp = client.get("/transactions/1")
    assert resp.status_code == 403


def test_stranger_cannot_access_payment_page(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/transactions/start/1")
    client.get("/auth/logout")

    register_and_login(client, "stranger1", "제3자")
    resp = client.get("/transactions/1/pay")
    assert resp.status_code == 403


def test_only_seller_can_transition_to_in_progress(client):
    _setup_paid_transaction(client)
    # 마지막으로 로그인된 사용자는 buyer1 (구매자가 판매자 권한 액션 시도)
    resp = client.post("/transactions/1/transition", data={"target_status": "in_progress"}, follow_redirects=True)
    assert "판매자만 거래를 시작할 수 있습니다".encode() in resp.data


def test_only_buyer_can_transition_to_completed(client):
    _setup_paid_transaction(client)
    client.get("/auth/logout")

    register_and_login(client, "seller1", "판매자1")
    client.post("/transactions/1/transition", data={"target_status": "in_progress"})

    resp = client.post("/transactions/1/transition", data={"target_status": "completed"}, follow_redirects=True)
    assert "구매자만 거래완료".encode() in resp.data


def test_invalid_status_transition_rejected(client):
    _setup_paid_transaction(client)
    # buyer1 로그인 상태. paid 상태에서 completed로 바로 건너뛰는 건 허용되지 않아야 한다
    resp = client.post("/transactions/1/transition", data={"target_status": "completed"}, follow_redirects=True)
    assert "허용되지 않는 상태 변경입니다".encode() in resp.data


def test_full_transaction_flow_and_review_updates_trust_score(client, app):
    _setup_paid_transaction(client)
    client.get("/auth/logout")

    register_and_login(client, "seller1", "판매자1")
    client.post("/transactions/1/transition", data={"target_status": "in_progress"})
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/transactions/1/transition", data={"target_status": "completed"})

    from app.models.product import Product, ProductStatus
    from app.models.user import User
    with app.app_context():
        assert Product.query.get(1).status == ProductStatus.SOLD
        seller_before = User.query.filter_by(username="seller1").first().trust_score

    client.post("/transactions/1/review", data={"rating": "5", "content": "좋은 거래였습니다"})

    with app.app_context():
        seller_after = User.query.filter_by(username="seller1").first().trust_score
        assert seller_after > seller_before


def test_duplicate_review_blocked(client):
    _setup_paid_transaction(client)
    client.get("/auth/logout")

    register_and_login(client, "seller1", "판매자1")
    client.post("/transactions/1/transition", data={"target_status": "in_progress"})
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/transactions/1/transition", data={"target_status": "completed"})
    client.post("/transactions/1/review", data={"rating": "5", "content": "좋아요"})

    resp = client.post("/transactions/1/review", data={"rating": "3", "content": "또씀"}, follow_redirects=True)
    assert "이미 후기를 작성했습니다".encode() in resp.data


def test_product_with_transaction_history_cannot_be_deleted(client):
    _setup_paid_transaction(client)
    client.get("/auth/logout")

    register_and_login(client, "seller1", "판매자1")
    resp = client.post("/products/1/delete", follow_redirects=True)
    assert "거래 이력이 있는 상품은 삭제할 수 없습니다".encode() in resp.data


def _complete_transaction_flow(client):
    """seller1/buyer1로 거래를 시작해 completed 상태까지 만든다. 마지막 로그인 상태는 buyer1."""
    _setup_paid_transaction(client)
    client.get("/auth/logout")

    register_and_login(client, "seller1", "판매자1")
    client.post("/transactions/1/transition", data={"target_status": "in_progress"})
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    client.post("/transactions/1/transition", data={"target_status": "completed"})


def test_stranger_cannot_access_review_page(client):
    _complete_transaction_flow(client)
    client.get("/auth/logout")

    register_and_login(client, "stranger1", "제3자")
    resp = client.get("/transactions/1/review")
    assert resp.status_code == 403


def test_review_blocked_before_transaction_completed(client):
    # completed 이전(paid) 상태에서 후기 URL에 직접 접근하면 상세 페이지로 리다이렉트되어야 한다.
    _setup_paid_transaction(client)
    # 마지막 로그인 상태는 buyer1, 거래 상태는 아직 paid (진행/완료 전)
    resp = client.get("/transactions/1/review", follow_redirects=True)
    assert "거래가 완료된 이후에만 후기를 남길 수 있습니다".encode() in resp.data


def test_completed_transaction_cannot_revert_to_in_progress(client):
    _complete_transaction_flow(client)
    # 마지막 로그인 상태는 buyer1. completed에서 in_progress로 되돌리려는 시도는 막혀야 한다.
    resp = client.post(
        "/transactions/1/transition",
        data={"target_status": "in_progress"},
        follow_redirects=True,
    )
    assert "허용되지 않는 상태 변경입니다".encode() in resp.data

    from app.models.transaction import Transaction, TransactionStatus
    with client.application.app_context():
        assert Transaction.query.get(1).status == TransactionStatus.COMPLETED


def test_trust_score_formula_cannot_reach_clamp_via_real_ratings(client, app):
    # 실제 서비스 흐름(평점 1~5)만으로는 매너온도 공식(base 36.5 ± 별점*5)이
    # 구조적으로 0 밑이나 99 위로 내려가거나 올라갈 수 없다(평점1: 26.5 / 평점5: 46.5).
    # 즉 클램프(max(0, min(99, ...)))는 현재 상수들 하에서는 실제로 도달 불가능한
    # 방어 코드다 - 이 사실 자체를 문서화해두는 테스트.
    _complete_transaction_flow(client)
    client.post("/transactions/1/review", data={"rating": "1", "content": "최저점"})

    from app.models.user import User
    with app.app_context():
        seller = User.query.filter_by(username="seller1").first()
        assert seller.trust_score == 26.5  # 0 근처에도 못 감


def test_trust_score_clamp_logic_itself_works_at_extremes(app):
    # 클램프 코드 자체는 정상 동작하는지, 실제 도달 가능 여부와 별개로 함수 단위로 검증한다.
    # TRUST_SCORE_PER_STAR을 일부러 크게 잡아서 극단값을 실제로 만들어본다.
    from app.transactions import routes as tx_routes
    from app.extensions import db
    from app.models.user import User, UserRole
    from app.models.product import Product
    from app.models.transaction import Transaction, TransactionStatus
    from app.models.review import Review

    with app.app_context():
        seller = User(username="clampseller", email="clampseller@example.com",
                      nickname="클램프", region="서울시", role=UserRole.USER)
        seller.set_password("abcd1234")
        buyer = User(username="clampbuyer", email="clampbuyer@example.com",
                     nickname="클램프구매자", region="서울시", role=UserRole.USER)
        buyer.set_password("abcd1234")
        db.session.add_all([seller, buyer])
        db.session.flush()

        product = Product(seller_id=seller.id, title="클램프상품", description="클램프 테스트 상품 설명",
                           price=1000, category="etc", condition="used")
        db.session.add(product)
        db.session.flush()

        tx = Transaction(product_id=product.id, buyer_id=buyer.id, seller_id=seller.id,
                          amount=1000, status=TransactionStatus.COMPLETED)
        db.session.add(tx)
        db.session.flush()

        review = Review(transaction_id=tx.id, reviewer_id=buyer.id, reviewee_id=seller.id,
                         rating=1, content="테스트용 최저점 후기")
        db.session.add(review)
        db.session.commit()

        original_per_star = tx_routes.TRUST_SCORE_PER_STAR
        tx_routes.TRUST_SCORE_PER_STAR = 50.0  # 계수를 키워서 실제로 경계값을 넘어보게 만든다
        try:
            tx_routes._recalculate_trust_score(seller.id)
            db.session.commit()
            refreshed = User.query.get(seller.id)
            assert refreshed.trust_score == 0.0  # 음수가 아니라 0에서 잘려야 한다
        finally:
            tx_routes.TRUST_SCORE_PER_STAR = original_per_star
