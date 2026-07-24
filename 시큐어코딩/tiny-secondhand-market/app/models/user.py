from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, bcrypt


class UserStatus:
    ACTIVE = "active"
    DORMANT = "dormant"   # 신고 누적으로 인한 휴면 처리
    BANNED = "banned"     # 관리자에 의한 영구 정지


class UserRole:
    USER = "user"
    ADMIN = "admin"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    nickname = db.Column(db.String(30), nullable=False)
    region = db.Column(db.String(50))
    profile_image = db.Column(db.String(255))  # 파일명만 저장, 경로는 서버가 관리

    trust_score = db.Column(db.Float, default=36.5, nullable=False)  # 매너온도 참고
    role = db.Column(db.String(10), default=UserRole.USER, nullable=False)
    status = db.Column(db.String(10), default=UserStatus.ACTIVE, nullable=False)
    report_count = db.Column(db.Integer, default=0, nullable=False)

    # 로그인 실패 잠금 정책용 필드
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, raw_password: str) -> None:
        # bcrypt 해싱 - 평문 비밀번호는 어떤 경우에도 저장하지 않는다
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def to_public_dict(self) -> dict:
        """타인이 볼 수 있는 프로필 정보만 골라서 내려준다.
        이메일, 로그인 실패 이력 같은 내부 정보는 절대 포함하지 않는다."""
        return {
            "id": self.id,
            "nickname": self.nickname,
            "region": self.region,
            "profile_image": self.profile_image,
            "trust_score": self.trust_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.username}>"
