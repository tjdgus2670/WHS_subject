from datetime import datetime
from app.extensions import db


class UserBlock(db.Model):
    __tablename__ = "user_blocks"

    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("blocker_id", "blocked_id", name="uq_block_pair"),
    )

    @staticmethod
    def exists_between(user_id_a: int, user_id_b: int) -> bool:
        """둘 중 누가 누구를 차단했든(방향 상관없이) 차단 관계가 있으면 True.
        채팅 시작/메시지 전송을 막을 때는 방향을 따지지 않는 게 자연스럽다."""
        return db.session.query(UserBlock.id).filter(
            db.or_(
                db.and_(UserBlock.blocker_id == user_id_a, UserBlock.blocked_id == user_id_b),
                db.and_(UserBlock.blocker_id == user_id_b, UserBlock.blocked_id == user_id_a),
            )
        ).first() is not None
