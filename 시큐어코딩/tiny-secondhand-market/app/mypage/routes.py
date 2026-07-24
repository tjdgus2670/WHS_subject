from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.product import Product, ProductStatus
from app.models.wish import Wish
from app.models.transaction import Transaction, TransactionStatus
from app.models.block import UserBlock
from app.mypage.images import save_profile_image, delete_profile_image_file, ImageValidationError
from app.utils.decorators import active_account_required

mypage_bp = Blueprint("mypage", __name__, url_prefix="/mypage")


@mypage_bp.route("/")
@login_required
def dashboard():
    stats = {
        "product_count": Product.query.filter_by(seller_id=current_user.id).count(),
        "selling_count": Product.query.filter_by(
            seller_id=current_user.id, status=ProductStatus.SELLING
        ).count(),
        "wish_count": Wish.query.filter_by(user_id=current_user.id).count(),
        "active_tx_count": Transaction.query.filter(
            (Transaction.buyer_id == current_user.id) | (Transaction.seller_id == current_user.id),
            Transaction.status.in_(
                [TransactionStatus.PENDING, TransactionStatus.PAID, TransactionStatus.IN_PROGRESS]
            ),
        ).count(),
        "blocked_count": UserBlock.query.filter_by(blocker_id=current_user.id).count(),
    }

    my_products = (
        Product.query.filter_by(seller_id=current_user.id)
        .order_by(Product.created_at.desc())
        .limit(6)
        .all()
    )

    return render_template("mypage/dashboard.html", stats=stats, my_products=my_products)


@mypage_bp.route("/profile-image", methods=["GET", "POST"])
@login_required
@active_account_required
def profile_image():
    if request.method == "POST":
        file = request.files.get("image")
        if not file or not file.filename:
            flash("이미지를 선택해주세요.", "danger")
            return redirect(url_for("mypage.profile_image"))

        try:
            filename = save_profile_image(file)
        except ImageValidationError as e:
            flash(str(e), "danger")
            return redirect(url_for("mypage.profile_image"))

        # 기존 이미지가 있었다면 새로 저장한 뒤 이전 파일을 정리한다
        old_filename = current_user.profile_image
        current_user.profile_image = filename
        db.session.commit()

        if old_filename:
            delete_profile_image_file(old_filename)

        flash("프로필 이미지가 변경되었습니다.", "success")
        return redirect(url_for("mypage.dashboard"))

    return render_template("mypage/profile_image.html")


@mypage_bp.route("/profile-image/delete", methods=["POST"])
@login_required
@active_account_required
def delete_profile_image():
    if current_user.profile_image:
        old_filename = current_user.profile_image
        current_user.profile_image = None
        db.session.commit()
        delete_profile_image_file(old_filename)

    flash("프로필 이미지를 삭제했습니다.", "info")
    return redirect(url_for("mypage.dashboard"))
