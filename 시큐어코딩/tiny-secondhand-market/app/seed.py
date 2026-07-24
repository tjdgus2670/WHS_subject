"""
데모/발표용 예시 데이터를 만드는 스크립트.

`flask seed-demo` 명령으로 실행한다. 이미 사용자 데이터가 있으면 아무것도 하지 않고
건너뛴다(중복 실행해도 안전하게). 처음부터 다시 만들고 싶으면 instance/app.db를
지우고 다시 실행하면 된다.

실제 서비스처럼 보이도록 사용자, 상품(이미지 포함), 찜, 1:1 채팅, 전체채팅, 거래,
후기, 신고(자동 차단 데모 포함), 사용자 차단, 관리자 로그까지 한 번에 만든다.
"""
import random
import uuid
import os

from flask import current_app
from PIL import Image, ImageDraw

from app.extensions import db
from app.models.user import User, UserRole
from app.models.product import Product, ProductImage, ProductStatus, ProductCondition
from app.models.wish import Wish
from app.models.chat import ChatRoom, Message, GlobalMessage
from app.models.report import Report, ReportTargetType, ReportStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.review import Review
from app.models.block import UserBlock
from app.models.admin_log import AdminLog

DEMO_PASSWORD = "abcd1234"

CATEGORY_COLORS = {
    "electronics": (61, 90, 128),
    "clothing": (176, 106, 179),
    "furniture": (148, 118, 78),
    "books": (90, 130, 100),
    "beauty": (219, 141, 168),
    "sports": (70, 150, 120),
    "kids": (240, 176, 90),
    "etc": (120, 120, 120),
}


def _lighten(color, amount=30):
    return tuple(min(c + amount, 255) for c in color)


def _make_product_placeholder(save_path, category):
    color = CATEGORY_COLORS.get(category, (130, 130, 130))
    img = Image.new("RGB", (600, 600), color=color)
    draw = ImageDraw.Draw(img)
    light = _lighten(color)
    for i in range(-600, 1200, 45):
        draw.line([(i, 0), (i + 600, 600)], fill=light, width=8)
    img.save(save_path, format="JPEG", quality=85)


def _make_avatar_placeholder(save_path, color):
    img = Image.new("RGB", (400, 400), color=color)
    draw = ImageDraw.Draw(img)
    draw.ellipse((50, 50, 350, 350), fill=_lighten(color, 45))
    img.save(save_path, format="JPEG", quality=85)


def _seed_product_image(product_id, category):
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "products")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    _make_product_placeholder(os.path.join(upload_dir, filename), category)
    return ProductImage(product_id=product_id, filename=filename, display_order=0)


def _set_profile_image(user, color):
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "profiles")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    _make_avatar_placeholder(os.path.join(upload_dir, filename), color)
    user.profile_image = filename


def run_seed():
    if User.query.first() is not None:
        print("이미 데이터가 있어 시딩을 건너뜁니다. (초기화하려면 instance/app.db를 지우고 다시 실행)")
        return

    def make_user(username, nickname, region, role=UserRole.USER, avatar_color=None):
        u = User(username=username, email=f"{username}@example.com", nickname=nickname, region=region, role=role)
        u.set_password(DEMO_PASSWORD)
        db.session.add(u)
        db.session.flush()
        if avatar_color:
            _set_profile_image(u, avatar_color)
        return u

    print("[1/8] 사용자 생성중...")
    admin = make_user("minji_kim", "민지", "서울시 마포구", role=UserRole.ADMIN, avatar_color=(219, 141, 168))
    junho = make_user("junho_lee", "준호", "서울시 강남구", avatar_color=(61, 90, 128))
    seoyeon = make_user("seoyeon_p", "서연", "서울시 은평구", avatar_color=(70, 150, 120))
    hyunwoo = make_user("hyunwoo_c", "현우", "서울시 마포구")
    yuna = make_user("yuna_jung", "유나", "서울시 마포구", avatar_color=(240, 176, 90))
    dongho = make_user("dongho_kim", "동호", "서울시 서대문구")
    sujin = make_user("sujin_han", "수진", "서울시 마포구")
    troll = make_user("noisy_guy", "시끄러운사람", "서울시 종로구")
    db.session.commit()

    print("[2/8] 상품 생성중...")
    products_spec = [
        (junho, "아이폰 13 팝니다 (128GB)", "거의 새 제품입니다. 케이스 끼고 사용해서 상태 좋아요.",
         650000, "electronics", ProductCondition.LIKE_NEW, ProductStatus.SELLING),
        (junho, "무선 이어폰 팝니다", "사용감 약간 있지만 음질 좋습니다.",
         45000, "electronics", ProductCondition.USED, ProductStatus.SELLING),
        (seoyeon, "원룸용 책상 팝니다", "이사 때문에 급처합니다. 직거래만 가능해요.",
         30000, "furniture", ProductCondition.USED, ProductStatus.RESERVED),
        (seoyeon, "겨울 패딩 팝니다 (L)", "한 시즌만 입었어요. 보풀 없습니다.",
         80000, "clothing", ProductCondition.LIKE_NEW, ProductStatus.SELLING),
        (hyunwoo, "아이패드 프로 11인치", "액정 깨끗합니다. 펜슬은 별도입니다.",
         550000, "electronics", ProductCondition.USED, ProductStatus.SOLD),
        (hyunwoo, "전공서적 세트 팝니다", "컴공 전공서적 5권 세트입니다.",
         15000, "books", ProductCondition.USED, ProductStatus.SELLING),
        (yuna, "요가매트 팝니다", "미개봉 새 제품입니다.",
         12000, "sports", ProductCondition.NEW, ProductStatus.SELLING),
        (yuna, "캠핑 의자 2개 세트", "몇 번 안 썼어요. 두 개 같이 드립니다.",
         25000, "sports", ProductCondition.LIKE_NEW, ProductStatus.SELLING),
        (dongho, "유아용 자전거", "아이가 커서 팝니다. 흠집 약간 있어요.",
         40000, "kids", ProductCondition.USED, ProductStatus.SELLING),
        (dongho, "스킨케어 세트 (미개봉)", "선물받았는데 안 써서 팝니다.",
         35000, "beauty", ProductCondition.NEW, ProductStatus.SELLING),
        (sujin, "블루투스 스피커", "가끔 잡음 있어서 저렴하게 드려요.",
         20000, "electronics", ProductCondition.USED, ProductStatus.SELLING),
        (sujin, "커피머신 팝니다", "이사 정리로 판매합니다.",
         60000, "etc", ProductCondition.USED, ProductStatus.RESERVED),
        (junho, "책장 팝니다", "3단 책장입니다. 튼튼해요.",
         35000, "furniture", ProductCondition.USED, ProductStatus.SELLING),
        (seoyeon, "런닝화 260mm", "몇 번 신어서 판매합니다.",
         30000, "sports", ProductCondition.LIKE_NEW, ProductStatus.SELLING),
        (hyunwoo, "노트북 거치대", "새 제품 미개봉입니다.",
         8000, "electronics", ProductCondition.NEW, ProductStatus.SELLING),
        (dongho, "의심스러운 초저가 노트북", "시세보다 너무 쌉니다. (신고 누적 자동차단 데모용)",
         50000, "electronics", ProductCondition.USED, ProductStatus.SELLING),
    ]

    products = []
    for seller, title, desc, price, category, condition, status in products_spec:
        p = Product(
            seller_id=seller.id, title=title, description=desc, price=price,
            category=category, condition=condition, status=status,
            view_count=random.randint(3, 120),
        )
        db.session.add(p)
        db.session.flush()
        db.session.add(_seed_product_image(p.id, category))
        products.append(p)
    db.session.commit()

    print("[3/8] 찜 생성중...")
    for user, product in [
        (seoyeon, products[0]), (yuna, products[0]), (dongho, products[0]),
        (junho, products[3]), (sujin, products[6]), (hyunwoo, products[7]),
    ]:
        db.session.add(Wish(user_id=user.id, product_id=product.id))
    db.session.commit()

    print("[4/8] 채팅 생성중...")
    room1 = ChatRoom(product_id=products[0].id, buyer_id=seoyeon.id, seller_id=junho.id)
    db.session.add(room1)
    db.session.flush()
    for sender, content in [
        (seoyeon, "안녕하세요! 아이폰 아직 판매중인가요?"),
        (junho, "네 아직 있습니다!"),
        (seoyeon, "혹시 직거래 가능한 위치가 어디쯤이신가요?"),
        (junho, "마포구 쪽에서 가능해요"),
        (seoyeon, "좋아요, 내일 오후 괜찮으세요?"),
    ]:
        db.session.add(Message(room_id=room1.id, sender_id=sender.id, content=content))

    room2 = ChatRoom(product_id=products[3].id, buyer_id=yuna.id, seller_id=seoyeon.id)
    db.session.add(room2)
    db.session.flush()
    for sender, content in [
        (yuna, "패딩 사이즈가 정확히 어떻게 되나요?"),
        (seoyeon, "라벨 기준 L인데 좀 크게 나온 편이에요"),
        (yuna, "혹시 사진 좀 더 볼 수 있을까요?"),
    ]:
        db.session.add(Message(room_id=room2.id, sender_id=sender.id, content=content))

    for sender, content in [
        (junho, "혹시 마포구 근처에서 직거래 하시는 분 계신가요?"),
        (yuna, "저 은평구인데 이 동네 중고거래 활발하네요 ㅎㅎ"),
        (dongho, "다들 좋은 거래 하세요~"),
        (sujin, "혹시 이 근처 벼룩시장 언제 열리는지 아시는 분?"),
        (hyunwoo, "다음 주말에 열린다고 들었어요!"),
    ]:
        db.session.add(GlobalMessage(sender_id=sender.id, content=content))
    db.session.commit()

    print("[5/8] 거래/후기 생성중...")
    tx1 = Transaction(
        product_id=products[4].id, buyer_id=dongho.id, seller_id=hyunwoo.id,
        amount=products[4].price, status=TransactionStatus.COMPLETED,
        mock_payment_id=f"mock_{uuid.uuid4().hex[:20]}",
    )
    db.session.add(tx1)
    db.session.flush()
    db.session.add(Review(transaction_id=tx1.id, reviewer_id=dongho.id, reviewee_id=hyunwoo.id,
                           rating=5, content="친절하고 상태도 설명대로였어요. 감사합니다!"))
    db.session.add(Review(transaction_id=tx1.id, reviewer_id=hyunwoo.id, reviewee_id=dongho.id,
                           rating=5, content="시간 약속 잘 지켜주셔서 좋았습니다."))
    hyunwoo.trust_score = 41.5
    dongho.trust_score = 41.5

    db.session.add(Transaction(
        product_id=products[2].id, buyer_id=hyunwoo.id, seller_id=seoyeon.id,
        amount=products[2].price, status=TransactionStatus.IN_PROGRESS,
        mock_payment_id=f"mock_{uuid.uuid4().hex[:20]}",
    ))
    db.session.add(Transaction(
        product_id=products[11].id, buyer_id=junho.id, seller_id=sujin.id,
        amount=products[11].price, status=TransactionStatus.PAID,
        mock_payment_id=f"mock_{uuid.uuid4().hex[:20]}",
    ))
    db.session.commit()

    print("[6/8] 신고 / 자동 차단 데모 생성중...")
    suspicious_product = products[-1]
    for reporter in [junho, seoyeon, hyunwoo, yuna, dongho]:
        db.session.add(Report(
            reporter_id=reporter.id, target_type=ReportTargetType.PRODUCT,
            target_id=suspicious_product.id, reason="fraud",
            description="시세보다 너무 저렴해서 사기가 의심됩니다.",
            status=ReportStatus.PENDING,
        ))
        suspicious_product.report_count += 1
    suspicious_product.status = ProductStatus.BLOCKED  # 신고 5건 누적 -> 자동 차단 데모

    db.session.add(Report(
        reporter_id=sujin.id, target_type=ReportTargetType.USER, target_id=troll.id,
        reason="abusive", description="채팅에서 욕설을 사용했습니다.",
        status=ReportStatus.PENDING,
    ))
    troll.report_count = 1  # 아직 임계치 미도달 -> 관리자 신고 큐에서 대기중으로 보임
    db.session.commit()

    print("[7/8] 관리자 조치 로그 생성중...")
    db.session.add(AdminLog(
        admin_id=admin.id, action="product_block", target_type="product",
        target_id=suspicious_product.id, detail=suspicious_product.title,
    ))
    db.session.commit()

    print("[8/8] 사용자 차단 데모 생성중...")
    db.session.add(UserBlock(blocker_id=sujin.id, blocked_id=troll.id))
    db.session.commit()

    print("\n시딩 완료!")
    print("모든 데모 계정의 비밀번호: " + DEMO_PASSWORD)
    print("관리자 계정: minji_kim")
    print("일반 계정: junho_lee, seoyeon_p, hyunwoo_c, yuna_jung, dongho_kim, sujin_han, noisy_guy")
