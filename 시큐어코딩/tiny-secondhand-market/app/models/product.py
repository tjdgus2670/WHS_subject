from datetime import datetime
from app.extensions import db


class ProductStatus:
    SELLING = "selling"
    RESERVED = "reserved"
    SOLD = "sold"
    BLOCKED = "blocked"   # 신고 누적으로 자동/수동 차단된 상태


class ProductCondition:
    NEW = "new"
    LIKE_NEW = "like_new"
    USED = "used"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(30), nullable=False, index=True)
    condition = db.Column(db.String(20), default=ProductCondition.USED, nullable=False)
    status = db.Column(db.String(20), default=ProductStatus.SELLING, nullable=False, index=True)

    view_count = db.Column(db.Integer, default=0, nullable=False)
    report_count = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    seller = db.relationship("User", backref="products")
    images = db.relationship(
        "ProductImage", backref="product", cascade="all, delete-orphan",
        order_by="ProductImage.display_order",
    )

    def is_visible(self) -> bool:
        # 차단된 상품은 목록/상세 어디에서도 노출되면 안 된다
        return self.status != ProductStatus.BLOCKED


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)  # 업로드 원본 파일명이 아니라 서버가 생성한 랜덤 파일명
    display_order = db.Column(db.Integer, default=0)
