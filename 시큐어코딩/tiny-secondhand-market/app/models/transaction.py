from datetime import datetime
from app.extensions import db


class TransactionStatus:
    PENDING = "pending"           # 거래 시작, 결제 전
    PAID = "paid"                 # Mock Payment 승인 완료
    IN_PROGRESS = "in_progress"   # 직거래/배송 진행중
    COMPLETED = "completed"       # 거래 완료 (후기 작성 가능해지는 시점)
    CANCELED = "canceled"

    # 서버에서만 강제하는 상태 전이 순서. 클라이언트가 임의 상태로 건너뛰지 못하게 막는 데 사용.
    ALLOWED_TRANSITIONS = {
        PENDING: {PAID, CANCELED},
        PAID: {IN_PROGRESS, CANCELED},
        IN_PROGRESS: {COMPLETED, CANCELED},
        COMPLETED: set(),
        CANCELED: set(),
    }


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # 금액은 반드시 서버가 상품 가격 기준으로 재계산해서 채운다 (클라이언트가 보낸 금액 신뢰 금지)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(15), default=TransactionStatus.PENDING, nullable=False, index=True)

    mock_payment_id = db.Column(db.String(64))  # Mock Payment API가 발급하는 가상 거래번호
    idempotency_key = db.Column(db.String(64), unique=True)  # 중복 결제 요청 방지

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship("Product")
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in TransactionStatus.ALLOWED_TRANSITIONS.get(self.status, set())
