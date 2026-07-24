from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.report import Report, ReportTargetType
from app.models.product import Product, ProductStatus
from app.models.user import User, UserStatus
from app.reports.forms import ReportForm

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/product/<int:product_id>", methods=["GET", "POST"])
@login_required
def report_product(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id == current_user.id:
        flash("본인 상품은 신고할 수 없습니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    # 이미 신고한 상품인지 확인 (Report 모델의 UniqueConstraint로도 DB단에서 막히지만,
    # 사용자에게 자연스러운 메시지를 보여주기 위해 미리 확인한다)
    already_reported = Report.query.filter_by(
        reporter_id=current_user.id, target_type=ReportTargetType.PRODUCT, target_id=product_id
    ).first()
    if already_reported:
        flash("이미 신고한 상품입니다.", "warning")
        return redirect(url_for("products.product_detail", product_id=product_id))

    form = ReportForm()
    if form.validate_on_submit():
        report = Report(
            reporter_id=current_user.id,
            target_type=ReportTargetType.PRODUCT,
            target_id=product_id,
            reason=form.reason.data,
            description=form.description.data,
        )
        db.session.add(report)

        product.report_count += 1
        threshold = current_app.config["PRODUCT_REPORT_BLOCK_THRESHOLD"]
        if product.report_count >= threshold and product.status != ProductStatus.BLOCKED:
            product.status = ProductStatus.BLOCKED

        db.session.commit()
        flash("신고가 접수되었습니다.", "success")
        return redirect(url_for("products.product_detail", product_id=product_id))

    return render_template(
        "reports/report_form.html",
        form=form,
        target_label=f"상품 · {product.title}",
        cancel_url=url_for("products.product_detail", product_id=product_id),
    )


@reports_bp.route("/user/<int:user_id>", methods=["GET", "POST"])
@login_required
def report_user(user_id):
    target_user = User.query.get_or_404(user_id)

    if target_user.id == current_user.id:
        flash("본인을 신고할 수 없습니다.", "danger")
        return redirect(url_for("index"))

    already_reported = Report.query.filter_by(
        reporter_id=current_user.id, target_type=ReportTargetType.USER, target_id=user_id
    ).first()
    if already_reported:
        flash("이미 신고한 사용자입니다.", "warning")
        return redirect(url_for("index"))

    form = ReportForm()
    if form.validate_on_submit():
        report = Report(
            reporter_id=current_user.id,
            target_type=ReportTargetType.USER,
            target_id=user_id,
            reason=form.reason.data,
            description=form.description.data,
        )
        db.session.add(report)

        target_user.report_count += 1
        threshold = current_app.config["USER_REPORT_DORMANT_THRESHOLD"]
        if target_user.report_count >= threshold and target_user.status == UserStatus.ACTIVE:
            target_user.status = UserStatus.DORMANT

        db.session.commit()
        flash("신고가 접수되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template(
        "reports/report_form.html",
        form=form,
        target_label=f"사용자 · {target_user.nickname}",
        cancel_url=url_for("index"),
    )
