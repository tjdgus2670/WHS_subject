import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY는 세션 서명, CSRF 토큰 생성에 쓰인다.
    # 반드시 환경변수로 주입하고, 코드에 하드코딩된 값을 그대로 쓰면 안 된다.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- 세션 / 쿠키 보안 설정 ---
    SESSION_COOKIE_HTTPONLY = True          # JS에서 document.cookie로 세션 쿠키 접근 불가 (XSS로 세션탈취 방지)
    SESSION_COOKIE_SAMESITE = "Lax"         # CSRF 방어 보조 (외부 사이트발 요청에는 쿠키 미전송)
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # --- 업로드 정책 (파일 업로드 취약점 대응) ---
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 요청 바디 전체 5MB 제한
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # --- 로그인 brute-force 방지 ---
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15

    # --- 신고 누적 자동 제재 임계치 ---
    PRODUCT_REPORT_BLOCK_THRESHOLD = 5
    USER_REPORT_DORMANT_THRESHOLD = 5

    # --- CSRF ---
    WTF_CSRF_TIME_LIMIT = None  # 폼 오래 열어놔도 토큰 만료로 실패하지 않게(개발 편의상)
