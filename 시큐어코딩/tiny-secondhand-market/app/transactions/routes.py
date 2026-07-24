from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.product import Product, ProductStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.review import Review
from app.models.user import User
from app.models.block import UserBlock
from app.transactions.forms import MockPaymentForm, ReviewForm
from app.payments.mock_gateway import charge, PaymentDeclinedError
from app.utils.decorators import active_account_required

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")

# 매너온도 계산에 쓰는 아주 단순한 상수. 실제 서비스처럼 정교한 알고리즘은 아니고,
# 평균 별점이 좋을수록 온도가 올라가는 정도만 보여주는 수준으로 잡았다.
TRUST_SCORE_BASE = 36.5
TRUST_SCORE_PER_STAR = 5.0


def _recalculate_trust_score(user_id: int) -> None:
    ratings = [r.rating for r in Review.query.filter_by(reviewee_id=user_id).all()]
    if not ratings:
        return
    avg_rating = sum(ratings) / len(ratings)
    score = TRUST_SCORE_BASE + (avg_rating - 3) * TRUST_SCORE_PER_STAR
    score = max(0.0, min(99.0, score))

    user = User.query.get(user_id)
    if user:
        user.trust_score = round(score, 1)


@transactions_bp.route("/start/<int:product_id>", methods=["POST"])
@login_required
@active_account_required
def start_transaction(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id == current_user.id:
        flash("본인 상품은 구매할 수 없습니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    if product.status != ProductStatus.SELLING:
        flash("이미 예약되었거나 판매완료된 상품입니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    if UserBlock.exists_between(current_user.id, product.seller_id):
        flash("차단 관계인 사용자와는 거래할 수 없습니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    # 이미 이 상품에 대해 내가 진행중인 거래가 있으면 그 결제 페이지로 이어서 보낸다
    existing = Transaction.query.filter(
        Transaction.product_id == product_id,
        Transaction.buyer_id == current_user.id,
        Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.PAID, TransactionStatus.IN_PROGRESS]),
    ).first()
    if existing:
        return redirect(url_for("transactions.pay", transaction_id=existing.id))

    tx = Transaction(
        product_id=product_id,
        buyer_id=current_user.id,
        seller_id=product.seller_id,
        amount=product.price,  # 금액은 서버가 상품 가격 기준으로 결정한다 (클라이언트 입력 신뢰 안 함)
        # 무료나눔은 카드 결제를 거치지 않는다. 다만 판매자가 거래를 시작하고 구매자가
        # 완료를 확정하는 이후 상태 흐름은 일반 거래와 동일하게 유지한다.
        status=TransactionStatus.PAID if product.price == 0 else TransactionStatus.PENDING,
    )
    db.session.add(tx)

    if product.price == 0:
        product.status = ProductStatus.RESERVED

    db.session.commit()

    if product.price == 0:
        flash("무료나눔 거래가 시작되었습니다. 판매자가 거래를 시작하면 완료할 수 있습니다.", "success")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    return redirect(url_for("transactions.pay", transaction_id=tx.id))


@transactions_bp.route("/<int:transaction_id>/pay", methods=["GET", "POST"])
@login_required
@active_account_required
def pay(transaction_id):
    tx = Transaction.query.get_or_404(transaction_id)
    if tx.buyer_id != current_user.id:
        # 결제 페이지는 구매자 본인만 접근 가능 (IDOR 방지)
        abort(403)

    if tx.status != TransactionStatus.PENDING:
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    # 과거에 생성된 0원 pending 거래도 결제 페이지를 거치지 않고 무료나눔으로 전환한다.
    # 새 거래는 start_transaction에서 바로 paid 상태로 만들기 때문에 이 분기는 호환용이다.
    if tx.amount == 0:
        tx.status = TransactionStatus.PAID
        tx.product.status = ProductStatus.RESERVED
        db.session.commit()
        flash("무료나눔 거래입니다. 카드 결제 없이 거래를 진행해주세요.", "success")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    form = MockPaymentForm()
    if form.validate_on_submit():
        try:
            payment_id = charge(tx.amount, form.card_number.data)
        except PaymentDeclinedError as e:
            flash(str(e), "danger")
            return render_template("transactions/pay.html", form=form, tx=tx)

        tx.status = TransactionStatus.PAID
        tx.mock_payment_id = payment_id
        tx.product.status = ProductStatus.RESERVED
        db.session.commit()

        flash("결제가 완료되었습니다.", "success")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    return render_template("transactions/pay.html", form=form, tx=tx)


@transactions_bp.route("/<int:transaction_id>")
@login_required
def detail(transaction_id):
    tx = Transaction.query.get_or_404(transaction_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        # 거래 당사자가 아니면 조회 자체를 막는다 (IDOR 방지)
        abort(403)

    my_review = Review.query.filter_by(transaction_id=tx.id, reviewer_id=current_user.id).first()
    return render_template("transactions/detail.html", tx=tx, my_review=my_review)


@transactions_bp.route("/<int:transaction_id>/transition", methods=["POST"])
@login_required
@active_account_required
def transition(transaction_id):
    tx = Transaction.query.get_or_404(transaction_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        abort(403)

    target = request.form.get("target_status", "")

    # 서버가 정의한 상태 전이표에 없는 값이면 무조건 거부 (클라이언트가 임의 상태로
    # 건너뛰는 것을 막기 위해 모델의 ALLOWED_TRANSITIONS를 그대로 사용한다)
    if not tx.can_transition_to(target):
        flash("허용되지 않는 상태 변경입니다.", "danger")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    # 상태별로 누가 바꿀 수 있는지도 제한한다
    if target == TransactionStatus.IN_PROGRESS and current_user.id != tx.seller_id:
        flash("판매자만 거래를 시작할 수 있습니다.", "danger")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    if target == TransactionStatus.COMPLETED and current_user.id != tx.buyer_id:
        flash("구매자만 거래완료 확정을 할 수 있습니다.", "danger")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    tx.status = target

    if target == TransactionStatus.COMPLETED:
        tx.product.status = ProductStatus.SOLD
    elif target == TransactionStatus.CANCELED:
        if tx.product.status == ProductStatus.RESERVED:
            tx.product.status = ProductStatus.SELLING

    db.session.commit()
    flash("거래 상태가 변경되었습니다.", "success")
    return redirect(url_for("transactions.detail", transaction_id=tx.id))


@transactions_bp.route("/")
@login_required
def my_transactions():
    txs = (
        Transaction.query
        .filter((Transaction.buyer_id == current_user.id) | (Transaction.seller_id == current_user.id))
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return render_template("transactions/list.html", txs=txs)


@transactions_bp.route("/<int:transaction_id>/review", methods=["GET", "POST"])
@login_required
def review(transaction_id):
    tx = Transaction.query.get_or_404(transaction_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        abort(403)

    if tx.status != TransactionStatus.COMPLETED:
        flash("거래가 완료된 이후에만 후기를 남길 수 있습니다.", "danger")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    existing = Review.query.filter_by(transaction_id=tx.id, reviewer_id=current_user.id).first()
    if existing:
        flash("이미 후기를 작성했습니다.", "warning")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    reviewee_id = tx.seller_id if current_user.id == tx.buyer_id else tx.buyer_id

    form = ReviewForm()
    if form.validate_on_submit():
        new_review = Review(
            transaction_id=tx.id,
            reviewer_id=current_user.id,
            reviewee_id=reviewee_id,
            rating=form.rating.data,
            content=form.content.data,
        )
        db.session.add(new_review)
        db.session.flush()

        _recalculate_trust_score(reviewee_id)

        db.session.commit()
        flash("후기가 등록되었습니다.", "success")
        return redirect(url_for("transactions.detail", transaction_id=tx.id))

    return render_template("transactions/review_form.html", form=form, tx=tx)
