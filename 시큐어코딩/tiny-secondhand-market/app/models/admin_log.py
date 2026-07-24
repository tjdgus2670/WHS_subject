from datetime import datetime
from app.extensions import db


class AdminLog(db.Model):
    """관리자가 어떤 조치를 언제 했는지 남기는 감사 로그.
    애플리케이션 레벨에서 수정/삭제 기능을 아예 제공하지 않는다 (append-only)."""
    __tablename__ = "admin_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)     # 예: "product_block", "user_ban"
    target_type = db.Column(db.String(20))
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
