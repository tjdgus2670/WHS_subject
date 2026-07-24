from datetime import datetime
from app.extensions import db


class ChatRoom(db.Model):
    """상품 하나에 대한 구매자-판매자 1:1 채팅방."""
    __tablename__ = "chat_rooms"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("product_id", "buyer_id", name="uq_room_product_buyer"),
    )

    product = db.relationship("Product")
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])

    def is_participant(self, user_id: int) -> bool:
        # 채팅방 접근 시 이 체크가 빠지면 채팅방 id만 바꿔서 남의 대화를 볼 수 있게 된다 (IDOR)
        return user_id in (self.buyer_id, self.seller_id)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)  # 출력 시 반드시 이스케이프 (XSS 방지)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    sender = db.relationship("User")


class GlobalMessage(db.Model):
    """동네 전체 공개 채팅."""
    __tablename__ = "global_messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    sender = db.relationship("User")
