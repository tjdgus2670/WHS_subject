from datetime import datetime
from app.extensions import db


class ReportTargetType:
    USER = "user"
    PRODUCT = "product"


class ReportStatus:
    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_type = db.Column(db.String(10), nullable=False)  # ReportTargetType
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)  # 출력 시 이스케이프 필요 (관리자 페이지에서 렌더링됨)
    status = db.Column(db.String(15), default=ReportStatus.PENDING, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 같은 사용자가 같은 대상을 반복 신고해서 자동 차단 로직을 어뷰징하는 것 방지
    __table_args__ = (
        db.UniqueConstraint("reporter_id", "target_type", "target_id", name="uq_report_once"),
    )
