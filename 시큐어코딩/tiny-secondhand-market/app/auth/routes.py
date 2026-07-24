from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models.user import User, UserStatus
from app.auth.forms import RegisterForm, LoginForm, PasswordChangeForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = RegisterForm()
    if form.validate_on_submit():
        # 아이디/이메일 중복 체크. SQLAlchemy ORM을 통해 쿼리하므로 SQL Injection 걱정 없음.
        existing = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        if existing:
            # "아이디가 중복입니다" / "이메일이 중복입니다"로 나눠 알려주면 계정 존재 여부를
            # 외부에서 유추(user enumeration)할 수 있어서 메시지를 하나로 통일한다.
            flash("이미 사용 중인 아이디 또는 이메일입니다.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            username=form.username.data,
            email=form.email.data,
            nickname=form.nickname.data,
            region=form.region.data,
        )
        user.set_password(form.password.data)  # bcrypt 해싱 - 평문 저장 안 함

        db.session.add(user)
        db.session.commit()

        flash("회원가입이 완료되었습니다. 로그인해주세요.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        # 계정이 없거나, 잠겨있거나, 비밀번호가 틀렸거나 - 전부 동일한 메시지로 응답한다.
        # (이유가 다르게 노출되면 공격자가 "이 아이디는 존재하는구나" 같은 정보를 얻을 수 있음)
        generic_error = "아이디 또는 비밀번호가 올바르지 않습니다."

        if user is None:
            flash(generic_error, "danger")
            return render_template("auth/login.html", form=form)

        if user.is_locked():
            # 잠금 여부를 다른 문구로 알려주면, 반복 시도 결과 메시지가 바뀌는지 관찰하는 것만으로
            # "이 아이디는 실제로 존재한다"를 외부에서 추측할 수 있다(계정 열거 방지를 위해
            # 존재하지 않는 계정/오답/잠김을 항상 동일한 문구로 응답한다).
            flash(generic_error, "danger")
            return render_template("auth/login.html", form=form)

        if user.status in (UserStatus.BANNED, UserStatus.DORMANT):
            # 정지든 휴면이든 동일한 메시지로 응답한다. 사유를 구체적으로 알려주면
            # 계정 상태를 외부에서 추측하는 데 쓰일 수 있다.
            flash(generic_error, "danger")
            return render_template("auth/login.html", form=form)

        if not user.check_password(form.password.data):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= current_app.config["MAX_LOGIN_ATTEMPTS"]:
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"]
                )
                user.failed_login_attempts = 0
            db.session.commit()
            flash(generic_error, "danger")
            return render_template("auth/login.html", form=form)

        # --- 로그인 성공 ---
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()

        # 세션 고정 공격(session fixation) 방지: 로그인 전 세션 데이터를 비우고 새로 시작한다.
        session.clear()
        login_user(user)
        session.permanent = True

        flash(f"{user.nickname}님, 환영합니다.", "success")

        # open redirect 방지: next 파라미터가 우리 서비스 내부 경로("/"로 시작)인지 확인
        next_page = request.args.get("next")
        if next_page and not next_page.startswith("/"):
            next_page = None
        return redirect(next_page or url_for("index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        # 세션이 탈취된 상태라도 현재 비밀번호를 모르면 바꿀 수 없도록 재확인한다.
        if not current_user.check_password(form.current_password.data):
            flash("현재 비밀번호가 올바르지 않습니다.", "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()

        # 비밀번호 변경 후에는 현재 세션도 새로 발급한다.
        # 참고: 지금 구조(클라이언트 서명 쿠키 세션)에서는 다른 기기에 남아있는 세션까지
        # 강제로 끊으려면 서버사이드 세션 저장소 + 버전 토큰 같은 장치가 별도로 필요하다.
        # 이번 과제 범위에서는 우선 현재 세션 재발급까지만 처리하고 한계로 남겨둔다.
        logout_user()
        session.clear()

        flash("비밀번호가 변경되었습니다. 다시 로그인해주세요.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/change_password.html", form=form)
