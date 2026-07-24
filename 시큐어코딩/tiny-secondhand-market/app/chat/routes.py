import time
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, abort, jsonify, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.chat import ChatRoom, Message, GlobalMessage
from app.models.product import Product
from app.models.user import UserStatus
from app.models.block import UserBlock
from app.utils.decorators import active_account_required

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

# 롱폴링 설정: 한 요청이 최대 이 시간(초) 동안 새 메시지를 기다리다가, 없으면 빈 응답을 준다.
# 클라이언트는 응답을 받는 즉시(또는 새 메시지를 받는 즉시) 곧바로 다음 폴링 요청을 보낸다.
LONG_POLL_TIMEOUT_SECONDS = 25
LONG_POLL_INTERVAL_SECONDS = 1
MAX_MESSAGE_LENGTH = 1000

# 채팅 도배(스팸) 방지: 정교한 rate limiter는 아니고, 최근 MESSAGE_BURST_WINDOW_SECONDS 안에
# MESSAGE_BURST_LIMIT개까지는 자유롭게 보낼 수 있지만 그 이상은 막는 단순한 "버스트 허용" 방식.
# 메시지 하나 보낼 때마다 무조건 대기시키는 게 아니라, 정상적인 대화 속도(몇 개는 빠르게 주고받는 것)는
# 허용하고 진짜 도배("이거이거이거이거...")만 막는 게 목적이다.
MESSAGE_BURST_LIMIT = 5
MESSAGE_BURST_WINDOW_SECONDS = 10


def _is_sending_too_fast(model, sender_id: int) -> bool:
    window_start = datetime.utcnow() - timedelta(seconds=MESSAGE_BURST_WINDOW_SECONDS)
    recent_count = (
        model.query.filter(model.sender_id == sender_id, model.created_at >= window_start)
        .count()
    )
    return recent_count >= MESSAGE_BURST_LIMIT


def _serialize_message(message):
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_nickname": message.sender.nickname if message.sender else "알 수 없음",
        "content": message.content,
        "created_at": message.created_at.strftime("%H:%M"),
        "is_mine": message.sender_id == current_user.id,
    }


def _get_message_body():
    data = request.get_json(silent=True) or {}
    content = str(data.get("content", "")).strip()
    return content


# ---------------- 1:1 채팅 ----------------

@chat_bp.route("/rooms")
@login_required
def room_list():
    rooms = (
        ChatRoom.query
        .filter((ChatRoom.buyer_id == current_user.id) | (ChatRoom.seller_id == current_user.id))
        .order_by(ChatRoom.created_at.desc())
        .all()
    )
    return render_template("chat/room_list.html", rooms=rooms)


@chat_bp.route("/start/<int:product_id>", methods=["POST"])
@login_required
@active_account_required
def start_room(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id == current_user.id:
        flash("본인 상품에는 채팅을 걸 수 없습니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    if UserBlock.exists_between(current_user.id, product.seller_id):
        flash("차단 관계인 사용자와는 채팅을 시작할 수 없습니다.", "danger")
        return redirect(url_for("products.product_detail", product_id=product_id))

    room = ChatRoom.query.filter_by(product_id=product_id, buyer_id=current_user.id).first()
    if room is None:
        room = ChatRoom(product_id=product_id, buyer_id=current_user.id, seller_id=product.seller_id)
        db.session.add(room)
        db.session.commit()

    return redirect(url_for("chat.room_detail", room_id=room.id))


@chat_bp.route("/rooms/<int:room_id>")
@login_required
def room_detail(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    if not room.is_participant(current_user.id):
        # 채팅방 id만 바꿔서 남의 1:1 대화를 열람하려는 시도 차단 (IDOR)
        abort(403)

    messages = (
        Message.query.filter_by(room_id=room_id).order_by(Message.id.asc()).all()
    )
    other_user = room.seller if room.buyer_id == current_user.id else room.buyer

    return render_template(
        "chat/room_detail.html",
        room=room,
        messages=[_serialize_message(m) for m in messages],
        other_user=other_user,
    )


@chat_bp.route("/rooms/<int:room_id>/messages", methods=["POST"])
@login_required
def send_room_message(room_id):
    if current_user.status != UserStatus.ACTIVE:
        return jsonify({"error": "휴면 또는 정지된 계정은 메시지를 보낼 수 없습니다."}), 403

    room = ChatRoom.query.get_or_404(room_id)
    if not room.is_participant(current_user.id):
        abort(403)

    other_id = room.seller_id if room.buyer_id == current_user.id else room.buyer_id
    if UserBlock.exists_between(current_user.id, other_id):
        return jsonify({"error": "차단 관계인 사용자와는 메시지를 주고받을 수 없습니다."}), 403

    if _is_sending_too_fast(Message, current_user.id):
        return jsonify({"error": "메시지를 너무 많이 보냈습니다. 잠시 후 다시 시도해주세요."}), 429

    content = _get_message_body()
    if not content:
        return jsonify({"error": "메시지를 입력해주세요."}), 400
    if len(content) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"메시지는 {MAX_MESSAGE_LENGTH}자를 넘을 수 없습니다."}), 400

    message = Message(room_id=room_id, sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()

    return jsonify({"message": _serialize_message(message)})


@chat_bp.route("/rooms/<int:room_id>/poll")
@login_required
def poll_room_messages(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    if not room.is_participant(current_user.id):
        abort(403)

    after_id = request.args.get("after_id", 0, type=int)
    deadline = time.time() + LONG_POLL_TIMEOUT_SECONDS

    while time.time() < deadline:
        # 트랜잭션을 매 반복마다 끝내야 다른 요청(다른 스레드)이 커밋한 새 메시지를
        # 지연 없이 조회할 수 있다. 커밋할 변경사항이 없어도 호출 자체는 안전하다.
        db.session.commit()

        messages = (
            Message.query
            .filter(Message.room_id == room_id, Message.id > after_id)
            .order_by(Message.id.asc())
            .all()
        )
        if messages:
            return jsonify({"messages": [_serialize_message(m) for m in messages]})

        time.sleep(LONG_POLL_INTERVAL_SECONDS)

    return jsonify({"messages": []})


# ---------------- 전체 채팅 ----------------

@chat_bp.route("/global")
@login_required
def global_chat():
    blocked_ids = {b.blocked_id for b in UserBlock.query.filter_by(blocker_id=current_user.id).all()}

    raw_messages = GlobalMessage.query.order_by(GlobalMessage.id.desc()).limit(100).all()
    visible = [m for m in raw_messages if m.sender_id not in blocked_ids]
    visible.reverse()
    visible = visible[-50:]

    return render_template("chat/global.html", messages=[_serialize_message(m) for m in visible])


@chat_bp.route("/global/messages", methods=["POST"])
@login_required
def send_global_message():
    if current_user.status != UserStatus.ACTIVE:
        return jsonify({"error": "휴면 또는 정지된 계정은 메시지를 보낼 수 없습니다."}), 403

    if _is_sending_too_fast(GlobalMessage, current_user.id):
        return jsonify({"error": "메시지를 너무 많이 보냈습니다. 잠시 후 다시 시도해주세요."}), 429

    content = _get_message_body()
    if not content:
        return jsonify({"error": "메시지를 입력해주세요."}), 400
    if len(content) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"메시지는 {MAX_MESSAGE_LENGTH}자를 넘을 수 없습니다."}), 400

    message = GlobalMessage(sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()

    return jsonify({"message": _serialize_message(message)})


@chat_bp.route("/global/poll")
@login_required
def poll_global_messages():
    after_id = request.args.get("after_id", 0, type=int)
    blocked_ids = {b.blocked_id for b in UserBlock.query.filter_by(blocker_id=current_user.id).all()}
    deadline = time.time() + LONG_POLL_TIMEOUT_SECONDS
    cursor = after_id

    while time.time() < deadline:
        db.session.commit()

        messages = (
            GlobalMessage.query
            .filter(GlobalMessage.id > cursor)
            .order_by(GlobalMessage.id.asc())
            .all()
        )
        if messages:
            cursor = messages[-1].id  # 차단된 메시지든 아니든 커서는 항상 전진시켜야 다음 폴링에서 같은 메시지를 반복해서 조회하지 않는다
            visible = [m for m in messages if m.sender_id not in blocked_ids]
            if visible:
                return jsonify({"messages": [_serialize_message(m) for m in visible], "last_id": cursor})
            # 새로 온 메시지가 전부 차단한 사용자 것이었다면, 대기하지 않고 바로 다음 구간을 확인한다
            continue

        time.sleep(LONG_POLL_INTERVAL_SECONDS)

    return jsonify({"messages": [], "last_id": cursor})
