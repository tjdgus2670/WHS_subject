from datetime import datetime
from app.extensions import db


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1~5
    content = db.Column(db.Text)  # 출력 시 이스케이프 필요 (XSS)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship("User", foreign_keys=[reviewer_id])

    # 거래 하나당 한 사람이 후기는 한 번만 남길 수 있게 제한
    __table_args__ = (
        db.UniqueConstraint("transaction_id", "reviewer_id", name="uq_review_once_per_tx"),
    )
