from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

from app.extensions import db
from app.models.user import User, UserStatus, UserRole


def is_admin_user(user_id: int) -> bool:
    """current_user.is_admin() 대신 이 함수를 쓰면 identity map 캐시와 무관하게
    항상 최신 role을 기준으로 판단한다. 상품 삭제 권한처럼 실제 접근 제어에
    쓰이는 곳에서는 이 함수를 쓰고, 화면에 배지 하나 보여주는 정도의 표시용
    체크는 current_user.is_admin()을 그대로 써도 크게 문제되지 않는다."""
    return db.session.query(User.role).filter_by(id=user_id).scalar() == UserRole.ADMIN


def active_account_required(view_func):
    """로그인된 세션이 남아있더라도, 그 사이 신고 누적 등으로 휴면/정지된 계정이면
    글쓰기/채팅/거래 같은 주요 액션을 막는다. 로그인 시점 체크만으로는 세션이 유지되는
    동안 상태가 바뀐 경우를 놓치기 때문에 액션 시점에도 다시 확인해야 한다.

    current_user 객체의 속성을 그대로 믿지 않고, status 컬럼만 매번 DB에서 새로
    조회한다. ORM 세션의 identity map 캐시 때문에 다른 경로로 이미 로드된 적 있는
    사용자 객체가 재사용되면 방금 반영된 정지/휴면 상태를 놓칠 수 있어서다."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated:
            fresh_status = db.session.query(User.status).filter_by(id=current_user.id).scalar()
            if fresh_status != UserStatus.ACTIVE:
                flash("휴면 또는 정지된 계정은 이 기능을 사용할 수 없습니다.", "danger")
                return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    """관리자 전용 라우트 보호. 프론트에서 메뉴를 숨기는 것과 별개로,
    서버에서 role을 다시 확인해야 URL 직접 접근/파라미터 조작으로 우회되지 않는다.
    role도 status와 동일한 이유로 DB에서 직접 새로 조회한다."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        fresh_role = db.session.query(User.role).filter_by(id=current_user.id).scalar()
        if fresh_role != UserRole.ADMIN:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapper
