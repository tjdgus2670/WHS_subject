from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.report import Report, ReportStatus, ReportTargetType
from app.models.product import Product, ProductStatus
from app.models.user import User, UserStatus
from app.models.admin_log import AdminLog
from app.utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _log_action(action, target_type, target_id, detail=None):
    db.session.add(AdminLog(
        admin_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    ))


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    stats = {
        "user_count": User.query.count(),
        "product_count": Product.query.count(),
        "pending_reports": Report.query.filter_by(status=ReportStatus.PENDING).count(),
        "dormant_users": User.query.filter_by(status=UserStatus.DORMANT).count(),
        "banned_users": User.query.filter_by(status=UserStatus.BANNED).count(),
        "blocked_products": Product.query.filter_by(status=ProductStatus.BLOCKED).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/reports")
@login_required
@admin_required
def report_queue():
    reports = (
        Report.query.filter_by(status=ReportStatus.PENDING)
        .order_by(Report.created_at.asc())
        .all()
    )

    items = []
    for r in reports:
        if r.target_type == ReportTargetType.PRODUCT:
            target = Product.query.get(r.target_id)
            label = target.title if target else "(삭제된 상품)"
            target_status = target.status if target else None
        else:
            target = User.query.get(r.target_id)
            label = target.nickname if target else "(삭제된 사용자)"
            target_status = target.status if target else None

        items.append({
            "report": r,
            "target": target,
            "label": label,
            "target_status": target_status,
        })

    return render_template("admin/report_queue.html", items=items)


@admin_bp.route("/reports/<int:report_id>/dismiss", methods=["POST"])
@login_required
@admin_required
def dismiss_report(report_id):
    report = Report.query.get_or_404(report_id)
    report.status = ReportStatus.DISMISSED

    if report.target_type == ReportTargetType.PRODUCT:
        target = Product.query.get(report.target_id)
    else:
        target = User.query.get(report.target_id)

    if target and target.report_count > 0:
        target.report_count -= 1

    _log_action("report_dismiss", report.target_type, report.target_id, f"report_id={report.id}")
    db.session.commit()
    flash("신고를 기각 처리했습니다.", "info")
    return redirect(url_for("admin.report_queue"))


@admin_bp.route("/products/<int:product_id>/block", methods=["POST"])
@login_required
@admin_required
def block_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.status = ProductStatus.BLOCKED
    Report.query.filter_by(
        target_type=ReportTargetType.PRODUCT, target_id=product_id, status=ReportStatus.PENDING
    ).update({"status": ReportStatus.REVIEWED})
    _log_action("product_block", ReportTargetType.PRODUCT, product_id, detail=product.title)
    db.session.commit()
    flash("상품을 차단했습니다.", "info")
    return redirect(url_for("admin.report_queue"))


@admin_bp.route("/products/<int:product_id>/unblock", methods=["POST"])
@login_required
@admin_required
def unblock_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.status = ProductStatus.SELLING
    _log_action("product_unblock", ReportTargetType.PRODUCT, product_id, detail=product.title)
    db.session.commit()
    flash("상품 차단을 해제했습니다.", "info")
    return redirect(url_for("admin.report_queue"))


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@login_required
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin():
        flash("관리자 계정은 정지할 수 없습니다.", "danger")
        return redirect(url_for("admin.report_queue"))

    user.status = UserStatus.BANNED
    Report.query.filter_by(
        target_type=ReportTargetType.USER, target_id=user_id, status=ReportStatus.PENDING
    ).update({"status": ReportStatus.REVIEWED})
    _log_action("user_ban", ReportTargetType.USER, user_id, detail=user.nickname)
    db.session.commit()
    flash("사용자를 정지했습니다.", "info")
    return redirect(url_for("admin.report_queue"))


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@login_required
@admin_required
def unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.status = UserStatus.ACTIVE
    user.report_count = 0  # 정상화 조치이므로 누적 카운트도 초기화한다 (재범 시 새로 카운트)
    _log_action("user_unban", ReportTargetType.USER, user_id, detail=user.nickname)
    db.session.commit()
    flash("사용자 상태를 정상으로 되돌렸습니다.", "info")
    return redirect(url_for("admin.report_queue"))


@admin_bp.route("/logs")
@login_required
@admin_required
def logs():
    entries = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(200).all()
    return render_template("admin/logs.html", entries=entries)
