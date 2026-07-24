def test_seed_creates_expected_demo_data(app):
    with app.app_context():
        from app.seed import run_seed
        from app.models import User, Product, Transaction, Report, ProductStatus

        run_seed()

        assert User.query.count() == 8
        assert Product.query.count() == 16
        assert Transaction.query.count() == 3
        assert Report.query.count() == 6

        blocked = Product.query.filter_by(status=ProductStatus.BLOCKED).count()
        assert blocked == 1  # 신고 누적 자동 차단 데모 상품


def test_seed_is_idempotent(app):
    with app.app_context():
        from app.seed import run_seed
        from app.models import User

        run_seed()
        first_count = User.query.count()

        run_seed()  # 이미 데이터가 있으면 아무것도 하지 않아야 한다
        second_count = User.query.count()

        assert first_count == second_count
