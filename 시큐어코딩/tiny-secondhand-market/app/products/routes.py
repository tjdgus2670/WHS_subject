from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, abort, session
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.product import Product, ProductImage, ProductStatus
from app.models.admin_log import AdminLog
from app.models.block import UserBlock
from app.models.wish import Wish
from app.models.transaction import Transaction
from app.products.forms import ProductForm, CATEGORY_CHOICES, SORT_CHOICES
from app.products.images import (
    save_product_image, delete_product_image_file,
    ImageValidationError, MAX_IMAGES_PER_PRODUCT,
)
from app.utils.decorators import active_account_required, is_admin_user

products_bp = Blueprint("products", __name__, url_prefix="/products")

PER_PAGE = 12


@products_bp.route("/")
def list_products():
    q = request.args.get("q", "", type=str).strip()
    category = request.args.get("category", "", type=str)
    sort = request.args.get("sort", "latest", type=str)
    page = request.args.get("page", 1, type=int)

    # 차단된 상품은 목록에서 항상 제외
    query = Product.query.filter(Product.status != ProductStatus.BLOCKED)

    if current_user.is_authenticated:
        blocked_ids = [
            b.blocked_id for b in UserBlock.query.filter_by(blocker_id=current_user.id).all()
        ]
        if blocked_ids:
            query = query.filter(~Product.seller_id.in_(blocked_ids))

    if q:
        # ORM 파라미터 바인딩 사용 - 검색어를 아무리 특이하게 넣어도 SQL Injection으로 이어지지 않는다
        like_pattern = f"%{q}%"
        query = query.filter(
            (Product.title.ilike(like_pattern)) | (Product.description.ilike(like_pattern))
        )

    if category:
        # 카테고리 값은 서버가 정의한 화이트리스트에 있을 때만 필터 조건으로 사용
        valid_categories = {c[0] for c in CATEGORY_CHOICES}
        if category in valid_categories:
            query = query.filter(Product.category == category)

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    return render_template(
        "products/list.html",
        products=pagination.items,
        pagination=pagination,
        q=q, category=category, sort=sort,
        category_choices=CATEGORY_CHOICES, sort_choices=SORT_CHOICES,
    )


@products_bp.route("/wishlist")
@login_required
def wishlist():
    wishes = (
        Wish.query.filter_by(user_id=current_user.id)
        .order_by(Wish.created_at.desc())
        .all()
    )
    products = [w.product for w in wishes if w.product and w.product.status != ProductStatus.BLOCKED]
    return render_template("products/wishlist.html", products=products)


@products_bp.route("/<int:product_id>/wish", methods=["POST"])
@login_required
def toggle_wish(product_id):
    Product.query.get_or_404(product_id)  # 존재하지 않는 상품이면 404

    existing = Wish.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("찜 목록에서 제거했습니다.", "info")
    else:
        db.session.add(Wish(user_id=current_user.id, product_id=product_id))
        db.session.commit()
        flash("찜 목록에 추가했습니다.", "success")

    return redirect(url_for("products.product_detail", product_id=product_id))


@products_bp.route("/new", methods=["GET", "POST"])
@login_required
@active_account_required
def create_product():
    form = ProductForm()
    if form.validate_on_submit():
        files = [f for f in request.files.getlist("images") if f and f.filename]

        if len(files) == 0:
            flash("이미지를 최소 1장 이상 등록해주세요.", "danger")
            return render_template("products/form.html", form=form, mode="create")

        if len(files) > MAX_IMAGES_PER_PRODUCT:
            flash(f"이미지는 최대 {MAX_IMAGES_PER_PRODUCT}장까지 등록할 수 있습니다.", "danger")
            return render_template("products/form.html", form=form, mode="create")

        saved_filenames = []
        try:
            for f in files:
                saved_filenames.append(save_product_image(f))
        except ImageValidationError as e:
            for fn in saved_filenames:  # 중간에 실패하면 이미 저장된 파일 정리
                delete_product_image_file(fn)
            flash(str(e), "danger")
            return render_template("products/form.html", form=form, mode="create")

        product = Product(
            seller_id=current_user.id,
            title=form.title.data,
            description=form.description.data,
            # "무료 나눔" 체크 시 서버에서도 가격을 0으로 강제한다 (JS가 꺼져 있어도 우회 불가하게)
            price=0 if form.is_free.data else form.price.data,
            category=form.category.data,
            condition=form.condition.data,
        )
        db.session.add(product)
        db.session.flush()  # product.id 확보

        for order, fn in enumerate(saved_filenames):
            db.session.add(ProductImage(product_id=product.id, filename=fn, display_order=order))

        db.session.commit()
        flash("상품이 등록되었습니다.", "success")
        return redirect(url_for("products.product_detail", product_id=product.id))

    return render_template("products/form.html", form=form, mode="create")


@products_bp.route("/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)

    is_owner = current_user.is_authenticated and current_user.id == product.seller_id
    is_admin = current_user.is_authenticated and is_admin_user(current_user.id)

    # 차단된 상품은 작성자 본인/관리자가 아니면 존재하지 않는 것처럼 처리
    if product.status == ProductStatus.BLOCKED and not is_owner and not is_admin:
        abort(404)

    is_wished = (
        current_user.is_authenticated and
        Wish.query.filter_by(user_id=current_user.id, product_id=product_id).first() is not None
    )
    wish_count = Wish.query.filter_by(product_id=product_id).count()

    # 접속할 때마다 조회수 증가 (본인 상품 제외). 같은 사람이 새로고침해도 계속 올라간다.
    if not is_owner:
        product.view_count += 1
        db.session.commit()

    return render_template(
        "products/detail.html", product=product, is_owner=is_owner, is_admin=is_admin,
        is_wished=is_wished, wish_count=wish_count,
    )


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@active_account_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    # IDOR 방지: 본인 상품이 아니면 접근 자체를 막는다. 수정 버튼을 화면에서 숨기는 것만으로는
    # URL을 직접 쳐서 들어오는 것까지 막을 수 없기 때문에 서버에서 반드시 다시 확인해야 한다.
    if product.seller_id != current_user.id:
        abort(403)

    form = ProductForm(obj=product)

    if form.validate_on_submit():
        product.title = form.title.data
        product.description = form.description.data
        product.price = 0 if form.is_free.data else form.price.data
        product.category = form.category.data
        product.condition = form.condition.data

        new_files = [f for f in request.files.getlist("images") if f and f.filename]
        if new_files:
            existing_count = len(product.images)
            if existing_count + len(new_files) > MAX_IMAGES_PER_PRODUCT:
                flash(f"이미지는 상품당 최대 {MAX_IMAGES_PER_PRODUCT}장까지 가능합니다.", "danger")
                return render_template("products/form.html", form=form, mode="edit", product=product)
            try:
                for f in new_files:
                    fn = save_product_image(f)
                    db.session.add(ProductImage(
                        product_id=product.id, filename=fn, display_order=len(product.images)
                    ))
            except ImageValidationError as e:
                flash(str(e), "danger")
                return render_template("products/form.html", form=form, mode="edit", product=product)

        db.session.commit()
        flash("상품 정보가 수정되었습니다.", "success")
        return redirect(url_for("products.product_detail", product_id=product.id))

    return render_template("products/form.html", form=form, mode="edit", product=product)


@products_bp.route("/<int:product_id>/images/<int:image_id>/delete", methods=["POST"])
@login_required
def delete_product_image(product_id, image_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id:
        abort(403)

    image = ProductImage.query.get_or_404(image_id)
    if image.product_id != product.id:
        # 이미지 id가 이 상품 소속이 아닌 경우도 IDOR 케이스라 막아야 한다
        # (다른 상품의 이미지 id를 넣어서 지우려는 시도)
        abort(404)

    delete_product_image_file(image.filename)
    db.session.delete(image)
    db.session.commit()
    flash("이미지가 삭제되었습니다.", "info")
    return redirect(url_for("products.edit_product", product_id=product.id))


@products_bp.route("/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id and not is_admin_user(current_user.id):
        abort(403)

    if Transaction.query.filter_by(product_id=product_id).first() is not None:
        flash("거래 이력이 있는 상품은 삭제할 수 없습니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    is_admin_action = product.seller_id != current_user.id and is_admin_user(current_user.id)
    if is_admin_action:
        # 본인 상품이 아닌데 삭제 권한이 있다는 건 관리자라는 뜻 - 감사 로그를 남긴다
        db.session.add(AdminLog(
            admin_id=current_user.id,
            action="product_delete",
            target_type="product",
            target_id=product.id,
            detail=product.title,
        ))

    for image in product.images:
        delete_product_image_file(image.filename)

    db.session.delete(product)
    db.session.commit()
    flash("상품이 삭제되었습니다.", "info")
    return redirect(url_for("products.list_products"))
