import os
import click
from flask import Flask, redirect, url_for

from config import Config
from app.extensions import db, login_manager, csrf, bcrypt, migrate


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # --- 확장 초기화 ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)  # 모든 POST/PUT/DELETE 요청에 CSRF 토큰 검증이 기본 적용된다
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id), populate_existing=True)

    # --- 블루프린트 등록 ---
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.products.routes import products_bp
    app.register_blueprint(products_bp)

    from app.chat.routes import chat_bp
    app.register_blueprint(chat_bp)

    from app.reports.routes import reports_bp
    app.register_blueprint(reports_bp)

    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp)

    from app.users.routes import users_bp
    app.register_blueprint(users_bp)

    from app.transactions.routes import transactions_bp
    app.register_blueprint(transactions_bp)

    from app.mypage.routes import mypage_bp
    app.register_blueprint(mypage_bp)

    # flask make-admin <username> 으로 특정 계정을 관리자로 지정할 수 있다
    @app.cli.command("make-admin")
    @click.argument("username")
    def make_admin(username):
        from app.models.user import User, UserRole
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"사용자 '{username}'을 찾을 수 없습니다.")
            return
        user.role = UserRole.ADMIN
        db.session.commit()
        print(f"'{username}'을(를) 관리자로 지정했습니다.")

    # flask seed-demo 로 데모/발표용 예시 데이터를 채울 수 있다
    @app.cli.command("seed-demo")
    def seed_demo():
        from app.seed import run_seed
        run_seed()

    # --- 공통 보안 헤더 ---
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"       # MIME 스니핑으로 인한 실행 방지
        response.headers["X-Frame-Options"] = "DENY"                 # 클릭재킹 방지
        response.headers["Referrer-Policy"] = "same-origin"
        # script-src는 명시하지 않아 default-src 'self'가 그대로 적용된다(인라인 스크립트 전면 차단).
        # 템플릿 쪽 인라인 <script>는 전부 제거하고 data-* 속성 + 외부 js 파일로 옮겨뒀다.
        # style-src만 아직 'unsafe-inline'을 허용 중 — 알려진 한계로 README에 기록.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
        )
        return response

    @app.route("/")
    def index():
        return redirect(url_for("products.list_products"))

    return app
