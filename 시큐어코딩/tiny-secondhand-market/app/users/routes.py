from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User
from app.models.product import Product, ProductStatus
from app.models.block import UserBlock
from app.models.review import Review

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/<int:user_id>")
def profile(user_id):
    profile_user = User.query.get_or_404(user_id)

    # 판매중인 상품만 공개 프로필에 노출 (차단된 상품은 제외)
    products = (
        Product.query
        .filter_by(seller_id=user_id)
        .filter(Product.status != ProductStatus.BLOCKED)
        .order_by(Product.created_at.desc())
        .limit(12)
        .all()
    )

    reviews = (
        Review.query.filter_by(reviewee_id=user_id)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )

    is_self = current_user.is_authenticated and current_user.id == user_id
    is_blocked_by_me = (
        current_user.is_authenticated and not is_self and
        UserBlock.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first() is not None
    )

    return render_template(
        "users/profile.html",
        profile_user=profile_user,
        products=products,
        reviews=reviews,
        is_self=is_self,
        is_blocked_by_me=is_blocked_by_me,
    )


@users_bp.route("/<int:user_id>/block", methods=["POST"])
@login_required
def block_user(user_id):
    if user_id == current_user.id:
        flash("본인을 차단할 수 없습니다.", "danger")
        return redirect(url_for("users.profile", user_id=user_id))

    target = User.query.get_or_404(user_id)

    existing = UserBlock.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if not existing:
        db.session.add(UserBlock(blocker_id=current_user.id, blocked_id=user_id))
        db.session.commit()

    flash(f"{target.nickname}님을 차단했습니다. 이제 서로 채팅을 걸 수 없고, 전체채팅에서도 보이지 않습니다.", "info")
    return redirect(url_for("users.profile", user_id=user_id))


@users_bp.route("/<int:user_id>/unblock", methods=["POST"])
@login_required
def unblock_user(user_id):
    existing = UserBlock.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    flash("차단을 해제했습니다.", "info")
    return redirect(url_for("users.profile", user_id=user_id))


@users_bp.route("/me/blocked")
@login_required
def blocked_list():
    blocks = (
        UserBlock.query.filter_by(blocker_id=current_user.id)
        .order_by(UserBlock.created_at.desc())
        .all()
    )
    blocked_users = [User.query.get(b.blocked_id) for b in blocks]
    blocked_users = [u for u in blocked_users if u is not None]
    return render_template("users/blocked_list.html", blocked_users=blocked_users)
