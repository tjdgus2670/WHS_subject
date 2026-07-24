import io

from tests.conftest import register_and_login, create_product


def test_create_product_requires_login(client):
    resp = client.get("/products/new", follow_redirects=True)
    assert "로그인이 필요합니다".encode() in resp.data


def test_fake_file_disguised_as_image_is_rejected(client):
    register_and_login(client, "seller1", "판매자1")
    fake_file = io.BytesIO(b"<script>this is not an image</script>")

    resp = client.post("/products/new", data={
        "title": "위장상품",
        "description": "악성파일 업로드 테스트용 설명입니다",
        "price": "1000",
        "category": "etc",
        "condition": "used",
        "images": (fake_file, "fake.jpg"),
    }, content_type="multipart/form-data", follow_redirects=True)

    assert "올바른 이미지 파일이 아닙니다".encode() in resp.data


def test_jpg_extension_with_valid_jpeg_content_is_accepted(client):
    from tests.conftest import make_test_image_bytes

    register_and_login(client, "seller1", "판매자1")
    resp = client.post("/products/new", data={
        "title": "JPG 이미지 상품",
        "description": "JPG 확장자 업로드 테스트입니다.",
        "price": "1000",
        "category": "etc",
        "condition": "used",
        "images": (make_test_image_bytes(fmt="JPEG"), "photo.jpg"),
    }, content_type="multipart/form-data", follow_redirects=True)

    assert resp.status_code == 200
    assert "JPG 이미지 상품".encode() in resp.data


def test_search_with_sql_injection_style_input_is_safe(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="아이폰 팝니다")

    resp = client.get("/products/", query_string={"q": "아이폰' OR '1'='1"})
    assert resp.status_code == 200
    # 파라미터 바인딩 덕분에 이상한 쿼리가 전체 상품을 다 긁어오지 않는다
    assert "아이폰 팝니다".encode() not in resp.data


def test_search_normal_keyword_still_works(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="아이폰 팝니다")

    resp = client.get("/products/", query_string={"q": "아이폰"})
    assert "아이폰 팝니다".encode() in resp.data


def test_edit_page_blocked_for_non_owner(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    resp = client.get("/products/1/edit")
    assert resp.status_code == 403


def test_delete_blocked_for_non_owner(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client)
    client.get("/auth/logout")

    register_and_login(client, "buyer1", "구매자1")
    resp = client.post("/products/1/delete")
    assert resp.status_code == 403


def test_owner_can_delete_own_product(client):
    register_and_login(client, "seller1", "판매자1")
    create_product(client)

    resp = client.post("/products/1/delete", follow_redirects=True)
    assert "상품이 삭제되었습니다".encode() in resp.data


def test_blocked_product_hidden_from_public_list(client, app):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="차단될상품")

    from app.models.product import Product, ProductStatus
    from app.extensions import db

    with app.app_context():
        p = Product.query.get(1)
        p.status = ProductStatus.BLOCKED
        db.session.commit()

    resp = client.get("/products/")
    assert "차단될상품".encode() not in resp.data


def test_blocked_product_returns_404_for_stranger(client, app):
    register_and_login(client, "seller1", "판매자1")
    create_product(client, title="차단될상품2")

    from app.models.product import Product, ProductStatus
    from app.extensions import db

    with app.app_context():
        p = Product.query.get(1)
        p.status = ProductStatus.BLOCKED
        db.session.commit()

    client.get("/auth/logout")
    register_and_login(client, "stranger1", "제3자")
    resp = client.get("/products/1")
    assert resp.status_code == 404


def test_free_product_can_be_registered_with_zero_price(client):
    # DataRequired는 0을 "입력 안 함"으로 취급해 무료나눔(가격 0원) 등록이 항상 막히던 버그.
    # InputRequired로 교체한 뒤에는 0원 등록이 정상적으로 통과해야 한다.
    register_and_login(client, "seller1", "판매자1")
    resp = client.post("/products/new", data={
        "title": "무료나눔 상품",
        "description": "안 쓰는 물건 무료로 나눔합니다",
        "price": "0",
        "category": "etc",
        "condition": "used",
        "images": (__import__("tests.conftest", fromlist=["make_test_image_bytes"]).make_test_image_bytes(), "free.png"),
    }, content_type="multipart/form-data", follow_redirects=True)

    assert resp.status_code == 200
    assert "상품이 등록되었습니다".encode() in resp.data
    assert "무료나눔".encode() in resp.data


def test_is_free_checkbox_forces_price_to_zero_serverside(client):
    # 체크박스가 켜졌는데 price 필드에 다른 값이 같이 전송돼도(JS 우회/조작 가정)
    # 서버가 price를 0으로 강제해야 한다.
    from tests.conftest import make_test_image_bytes

    register_and_login(client, "seller1", "판매자1")
    resp = client.post("/products/new", data={
        "title": "무료나눔 강제상품",
        "description": "체크박스 서버 강제 테스트용 설명입니다",
        "price": "50000",  # 체크박스가 켜졌으니 이 값은 무시돼야 함
        "is_free": "y",
        "category": "etc",
        "condition": "used",
        "images": (make_test_image_bytes(), "free2.png"),
    }, content_type="multipart/form-data", follow_redirects=True)

    assert resp.status_code == 200

    from app.models.product import Product
    with client.application.app_context():
        p = Product.query.filter_by(title="무료나눔 강제상품").first()
        assert p is not None
        assert p.price == 0


def test_decompression_bomb_image_is_rejected_gracefully(client, monkeypatch):
    # 실제로 기가픽셀급 이미지를 만들면 테스트 자체가 메모리를 과하게 먹으니,
    # Pillow의 MAX_IMAGE_PIXELS를 테스트 시점에만 아주 작게 낮춰서 동일한 코드 경로
    # (DecompressionBombError)를 재현한다. 이 값이 원래보다 작으면 평범한 이미지도
    # "폭탄"으로 취급되므로, 우리 코드가 500이 아니라 깔끔한 검증 실패로 처리하는지만 본다.
    import app.products.images as images_module
    monkeypatch.setattr(images_module.Image, "MAX_IMAGE_PIXELS", 100)

    from tests.conftest import make_test_image_bytes

    register_and_login(client, "seller1", "판매자1")
    resp = client.post("/products/new", data={
        "title": "디코딩폭탄상품",
        "description": "디코딩 폭탄 방어 테스트용 설명입니다",
        "price": "1000",
        "category": "etc",
        "condition": "used",
        "images": (make_test_image_bytes(size=(50, 50)), "bomb.png"),
    }, content_type="multipart/form-data", follow_redirects=True)

    assert resp.status_code == 200  # 500이 아니라 정상적인 폼 재렌더링이어야 함
    # 실제로는 Pillow가 img.verify() 이전, Image.open() 시점에 이미 DecompressionBombError를
    # 던지기 때문에 (기존에 있던 첫 번째 try/except가 잡아서) 이 일반 메시지로 나온다.
    # 두 번째 try/except(제가 이번에 추가한 것)에서 만든 "이미지 해상도가 너무 크거나..."
    # 메시지는 이 경로에서는 도달하지 않는다 - 어느 쪽이든 500이 아니라 깔끔하게 막히는 게 핵심.
    assert "올바른 이미지 파일이 아닙니다".encode() in resp.data


def test_jpg_and_jpeg_extensions_both_accepted(client):
    # Pillow는 파일 내용을 보고 포맷을 판별하기 때문에(확장자 아님) .jpg/.jpeg 둘 다
    # 실제로는 동일하게 "JPEG" 포맷으로 인식된다. 확장자별로 다르게 취급되지 않는지 확인.
    from tests.conftest import make_test_image_bytes

    register_and_login(client, "seller1", "판매자1")
    for ext in ("jpg", "jpeg"):
        resp = client.post("/products/new", data={
            "title": f"{ext}확장자상품",
            "description": f"{ext} 확장자 업로드 테스트용 설명입니다",
            "price": "1000",
            "category": "etc",
            "condition": "used",
            "images": (make_test_image_bytes(fmt="JPEG"), f"photo.{ext}"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert resp.status_code == 200
        assert "상품이 등록되었습니다".encode() in resp.data
