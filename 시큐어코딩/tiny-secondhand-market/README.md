# Tiny Secondhand Shopping Platform — 기술 구현 보고서

**과목**: Secure Coding
**과제명**: 중고거래 플랫폼(Tiny Secondhand Shopping Platform) 설계 및 구현
**참고 서비스**: 당근마켓, 중고나라

---

## 1. 프로젝트 개요

본 프로젝트는 당근마켓·중고나라와 같은 지역 기반 중고거래 서비스를 축소한 형태로 구현한
웹 애플리케이션이다. 목적은 단순히 CRUD 기능을 갖춘 게시판을 만드는 것이 아니라, 회원가입부터
결제까지 이어지는 실제 서비스 흐름 속에서 발생할 수 있는 대표적인 웹 취약점(SQL Injection,
XSS, CSRF, IDOR, Broken Access Control, 파일 업로드 취약점, 세션 취약점, 개인정보 유출)을
직접 방어하는 코드를 작성하고, 그 방어가 실제로 동작하는지 자동화된 테스트로 검증하는 데 있다.

개발 전 단계에서 별도로 작성한 요구사항 분석 문서(`requirements.md`)를 기준으로, 기본 요구사항
18개와 추가 기능 11개, 총 29개 항목을 전부 구현했다.

---

## 2. 기술 스택

| 구분 | 선택 | 비고 |
|---|---|---|
| 언어/프레임워크 | Python 3.12 / Flask 3.0 | 기존에 Flask 사용 경험이 있어 프레임워크 학습보다 보안 로직 구현에 집중하기 위해 선택 |
| ORM | Flask-SQLAlchemy | 파라미터 바인딩이 기본이라 SQL Injection을 원천적으로 차단 |
| 인증/세션 | Flask-Login | 세션 기반 로그인 상태 관리 |
| 폼/CSRF | Flask-WTF (WTForms + CSRFProtect) | 서버사이드 입력 검증과 CSRF 토큰 발급을 한 번에 처리 |
| 비밀번호 해시 | Flask-Bcrypt | bcrypt 알고리즘으로 단방향 해시 |
| 이미지 처리 | Pillow | 업로드된 파일이 실제 이미지인지 검증하고 재인코딩 |
| DB | SQLite | 개발/과제 범위에 맞춰 설치 없이 바로 실행 가능한 파일 기반 DB. `SQLALCHEMY_DATABASE_URI`만 바꾸면 PostgreSQL 등으로 교체 가능한 구조 |
| 프론트엔드 | Jinja2 서버 렌더링 + Vanilla JS(fetch) | SPA 대신 서버 렌더링을 택해 세션 기반 인증·CSRF 처리를 단순하게 유지 |
| 실시간 채팅 | 롱폴링 (Long Polling) | 웹소켓 대비 별도 서버(Flask-SocketIO + eventlet 등) 없이 구현 가능해 학습 프로젝트 범위에 적합 |
| 테스트 | pytest + Flask test client | 인메모리가 아닌 파일 기반 SQLite를 요청마다 새로 생성해 테스트 간 격리 보장 |

### Flask를 선택한 이유

Node.js도 검토했으나, (1) 이미 Flask 사용 경험이 있어 프레임워크 자체와 씨름하는 시간을
줄이고 보안 로직 구현에 시간을 더 쓸 수 있고, (2) SQLAlchemy(ORM)·Flask-WTF(CSRF)·
Flask-Login(세션)·Bcrypt(해시)로 요구사항 문서의 보안 항목 대부분을 검증된 라이브러리로
커버할 수 있으며, (3) 실시간 채팅은 롱폴링으로 대체 가능해 결정적 단점이 되지 않는다고
판단해 Flask로 진행했다.

---

## 3. 시스템 아키텍처

### 3.1 디렉토리 구조

```
tiny-secondhand-market/
├── app/
│   ├── __init__.py          # Application Factory, 블루프린트 등록, 보안 헤더, CLI 명령
│   ├── extensions.py        # db, login_manager, csrf, bcrypt, migrate 인스턴스
│   ├── models/               # SQLAlchemy 모델 12개
│   ├── auth/                 # 회원가입, 로그인, 로그아웃, 비밀번호 변경
│   ├── products/              # 상품 등록/조회/검색/수정/삭제, 이미지 검증, 찜
│   ├── chat/                  # 1:1 채팅, 전체채팅 (롱폴링)
│   ├── reports/               # 신고 접수, 누적 자동 제재
│   ├── admin/                 # 관리자 대시보드, 신고 큐, 감사 로그
│   ├── users/                 # 공개 프로필, 사용자 차단
│   ├── transactions/          # 거래 시작, Mock 결제, 상태 전이, 후기
│   ├── payments/              # Mock Payment Gateway
│   ├── mypage/                 # 마이페이지 허브, 프로필 이미지 업로드
│   ├── utils/                  # 공통 데코레이터 (계정 상태/관리자 권한 체크)
│   ├── seed.py                 # 데모/발표용 예시 데이터 시딩 스크립트 (flask seed-demo)
│   ├── templates/              # Jinja2 템플릿 (모듈별 하위 폴더)
│   └── static/                 # CSS, JS, 업로드 파일 저장 경로
├── tests/                     # pytest 테스트 (도메인별 6개 파일 + CSRF 전용)
├── config.py                  # 환경변수 기반 설정
├── run.py                     # 앱 실행 진입점
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

### 3.2 Application Factory 패턴

`app/__init__.py`의 `create_app()` 함수가 Flask 앱 인스턴스를 생성하고, 확장(db, login_manager,
csrf, bcrypt, migrate)을 초기화한 뒤 블루프린트 8개를 등록한다. 이 패턴을 쓴 이유는 테스트할 때
운영 설정과 다른 `Config` 클래스(예: 인메모리 대신 임시 파일 DB, CSRF 비활성화)를 주입해서
완전히 격리된 앱 인스턴스를 매 테스트마다 새로 만들 수 있기 때문이다. 실제로 `tests/conftest.py`의
`app` fixture가 이 구조를 그대로 활용한다.

### 3.3 블루프린트 구성

| 블루프린트 | URL prefix | 담당 기능 |
|---|---|---|
| `auth` | `/auth` | 회원가입, 로그인, 로그아웃, 비밀번호 변경 |
| `products` | `/products` | 상품 CRUD, 검색, 찜 |
| `chat` | `/chat` | 1:1 채팅, 전체채팅, 롱폴링 |
| `reports` | `/reports` | 신고 접수 |
| `admin` | `/admin` | 관리자 대시보드, 신고 처리, 감사 로그 |
| `users` | `/users` | 공개 프로필, 사용자 차단 |
| `transactions` | `/transactions` | 거래, Mock 결제, 상태 전이, 후기 |
| `mypage` | `/mypage` | 마이페이지 허브, 프로필 이미지 |

각 블루프린트는 `routes.py`(라우트), `forms.py`(WTForms 폼, 있는 경우), 그리고 필요한 경우
별도 유틸(`images.py` 등)로 구성해 관심사를 분리했다.

---

## 4. 데이터베이스 설계

총 12개 테이블로 구성했다. 모든 외래키는 `db.relationship`으로 양방향 접근이 가능하도록
연결했고, 필요한 곳에는 `UniqueConstraint`를 걸어 애플리케이션 로직뿐 아니라 DB 레벨에서도
중복을 막았다.

### 4.1 `users`

| 필드 | 타입 | 설명 |
|---|---|---|
| id | Integer PK | |
| username | String(30), UNIQUE | 로그인 아이디 |
| email | String(120), UNIQUE | |
| password_hash | String(255) | bcrypt 해시, 평문 저장 안 함 |
| nickname | String(30) | |
| region | String(50) | 동네 |
| profile_image | String(255) | 서버가 생성한 랜덤 파일명만 저장 |
| trust_score | Float, default 36.5 | 매너온도. 후기 평균으로 재계산 |
| role | String(10), default `user` | `user` / `admin` |
| status | String(10), default `active` | `active` / `dormant` / `banned` |
| report_count | Integer, default 0 | 누적 신고 수 |
| failed_login_attempts | Integer, default 0 | 로그인 실패 카운트 |
| locked_until | DateTime | 잠금 해제 시각 |
| created_at / updated_at | DateTime | |

### 4.2 `products` / `product_images`

`products`: id, seller_id(FK), title, description, price, category, condition(`new`/`like_new`/`used`),
status(`selling`/`reserved`/`sold`/`blocked`), view_count, report_count, created_at, updated_at.

`product_images`: id, product_id(FK), filename(랜덤 생성), display_order. 상품 1개당 여러 이미지를
1:N으로 연결하고 `cascade="all, delete-orphan"`으로 상품 삭제 시 이미지 레코드도 함께 정리한다.

### 4.3 `wishes`

user_id + product_id 조합에 `UniqueConstraint`를 걸어 같은 상품을 두 번 찜할 수 없게 했다.

### 4.4 `chat_rooms` / `messages` / `global_messages`

`chat_rooms`: product_id, buyer_id, seller_id, created_at. `(product_id, buyer_id)`에 유니크 제약을
걸어 같은 상품에 대해 같은 구매자가 채팅방을 중복 생성하지 못하게 했다.
`messages`: room_id, sender_id, content, created_at. `global_messages`는 room 개념 없이 sender_id,
content, created_at만 가진다.

### 4.5 `reports`

reporter_id, target_type(`product`/`user`), target_id, reason, description, status(`pending`/
`reviewed`/`dismissed`), created_at. `(reporter_id, target_type, target_id)`에 유니크 제약을 걸어
같은 대상을 반복 신고해 자동 차단 로직을 어뷰징하는 것을 막는다.

### 4.6 `transactions` / `reviews`

`transactions`: product_id, buyer_id, seller_id, amount(서버가 상품 가격 기준으로 채움),
status(`pending`/`paid`/`in_progress`/`completed`/`canceled`), mock_payment_id, idempotency_key,
created_at, updated_at. 상태 전이는 클래스 변수 `ALLOWED_TRANSITIONS` 딕셔너리로 명시적으로
정의해 클라이언트가 임의 상태로 건너뛰지 못하게 했다.

`reviews`: transaction_id, reviewer_id, reviewee_id, rating(1~5), content, created_at.
`(transaction_id, reviewer_id)`에 유니크 제약을 걸어 거래 하나당 후기를 한 번만 남길 수 있다.

### 4.7 `user_blocks` / `admin_logs`

`user_blocks`: blocker_id, blocked_id, created_at. `(blocker_id, blocked_id)` 유니크 제약.
`admin_logs`: admin_id, action, target_type, target_id, detail, created_at. 수정/삭제 API를 따로
두지 않는 append-only 구조로 설계했다.

---

## 5. 기능별 상세 구현

### 5.1 계정과 인증

#### 회원가입 / 로그인 / 로그아웃 (`app/auth/routes.py`)

- `RegisterForm`(WTForms)이 아이디(4~20자, 영문/숫자/`_`), 이메일 형식, 닉네임(2~20자),
  비밀번호(8자 이상 + 영문·숫자 혼합)를 서버사이드에서 검증한다.
- 회원가입 시 아이디/이메일 중복 여부를 하나의 쿼리로 확인하고, 어느 쪽이 중복인지 구분하지
  않고 "이미 사용 중인 아이디 또는 이메일입니다"로 통일해 계정 열거(user enumeration) 공격을
  방지한다.
- 로그인 실패 시에도 "아이디 없음 / 비밀번호 틀림 / 계정 잠김 / 정지·휴면"을 구분하지 않고
  동일한 메시지로 응답한다(단, 잠금 상태만 별도 문구를 쓰되 계정 존재 여부는 드러내지 않는다).
- 로그인 성공 시 `session.clear()` 후 `login_user()`를 호출해 세션을 새로 발급한다(세션 고정
  공격 방지). `next` 파라미터는 `/`로 시작하는 내부 경로인지 확인해 Open Redirect를 막는다.
- 로그인 5회 실패 시 15분간 계정을 잠근다(`User.failed_login_attempts`, `locked_until`).

#### 비밀번호 변경 (`/auth/password`)

현재 비밀번호를 다시 확인한 뒤에만 변경을 허용한다(세션 탈취만으로는 비밀번호를 바꿀 수
없게). 변경 성공 시 현재 세션을 로그아웃 처리해 재로그인을 요구한다.

#### 프로필 조회 (`app/users/routes.py`, `/users/<id>`)

공개 프로필은 `User.to_public_dict()`처럼 화이트리스트 방식으로 노출 필드를 제한한다(이메일,
로그인 실패 이력 등 내부 정보는 절대 포함하지 않음). 판매중인 상품 최근 12개와 받은 후기
최근 10개를 함께 보여준다.

#### 마이페이지 (`app/mypage/routes.py`, `/mypage/`)

내 상품 수, 판매중인 상품 수, 찜한 상품 수, 진행중 거래 수, 차단한 사용자 수를 집계해서
대시보드로 보여주고, 찜목록·거래내역·차단목록·비밀번호 변경으로 가는 진입점을 모아둔다.
이전에는 이 링크들이 상단 네비게이션에 전부 나열돼 있었는데, 기능이 늘어나면서 마이페이지
허브로 모으고 네비게이션은 핵심 동선(홈, 상품 등록, 채팅, 마이페이지)만 남기도록 정리했다.

#### 프로필 이미지 업로드 (`app/mypage/images.py`)

상품 이미지와 동일한 원칙으로 검증한다. 확장자나 `Content-Type` 헤더는 클라이언트가 조작할
수 있으므로 신뢰하지 않고, Pillow로 실제로 열어본 뒤(`Image.verify()`) 정사각형으로 크롭
(`ImageOps.fit`)하고 JPEG로 재인코딩해 랜덤 파일명(`uuid4().hex`)으로 저장한다. 기존 이미지가
있으면 새 이미지 저장 성공 후 이전 파일을 삭제해 디스크에 파일이 쌓이지 않게 한다.

#### 사용자 신뢰도(매너온도) (`app/transactions/routes.py::_recalculate_trust_score`)

거래 완료 후 후기가 등록될 때마다, 해당 사용자가 받은 모든 후기의 평균 별점을 기준으로
`trust_score = 36.5 + (평균별점 - 3) * 5`를 계산해 0~99 사이로 clamp한다. 정교한 알고리즘은
아니지만, "후기가 좋을수록 온도가 올라간다"는 매너온도 컨셉을 단순하게 구현한 것이다.

#### 사용자 차단 (`app/users/routes.py`, `app/models/block.py`)

신고와는 별개로, 특정 사용자와의 상호작용을 개인 단위로 차단하는 기능이다.
`UserBlock.exists_between(a, b)`가 방향에 상관없이 둘 사이에 차단 관계가 있는지 확인하며,
이 함수는 세 군데에서 실제로 사용된다.

1. **채팅 시작 차단** — `chat.start_room`에서 차단 관계면 채팅방 생성 자체를 막는다.
2. **메시지 전송 차단** — `chat.send_room_message`에서도 동일하게 재확인한다(채팅방이 만들어진
   이후 차단이 생긴 경우까지 커버).
3. **전체채팅 필터링** — `chat.global_chat`, `chat.poll_global_messages`에서 내가 차단한 사용자의
   메시지를 응답에서 제외한다. 이때 롱폴링의 `after_id` 커서를 "화면에 보여준 마지막 메시지"가
   아니라 "실제로 확인한 마지막 메시지(차단된 것 포함)"로 전진시켜야, 차단한 사용자가 메시지를
   계속 보낼 때 폴링이 매번 25초를 꽉 채우고서야 다음 메시지를 확인하는 문제를 막을 수 있다.
   (자세한 구현은 5.3절 참고)

또한 상품 목록(`products.list_products`)에서도 차단한 판매자의 상품을 결과에서 제외한다.

---

### 5.2 상품

#### 상품 등록 / 수정 / 삭제 (`app/products/routes.py`)

- `ProductForm`이 제목(2~100자), 설명(5~2000자), 가격(0~1억원), 카테고리·상태(서버가 정의한
  `SelectField` 값만 허용)를 검증한다. **무료나눔**은 "무료 나눔" 체크박스(`is_free`)를 켜면
  JS가 가격을 0으로 고정하고, 서버에서도 `is_free`가 켜져 있으면 가격을 0으로 강제한다(JS를
  꺼도 우회되지 않게 이중 처리). 가격 필드는 `DataRequired` 대신 `InputRequired`를 쓰는데,
  `DataRequired`는 0을 "입력 안 함"으로 취급해서 무료나눔 등록 자체가 항상 실패하던 버그가
  있었다.
- 무료나눔(가격 0원) 상품은 거래 시작 시 Mock 결제를 거치지 않고 곧바로 거래가 진행된다
  (`app/transactions/routes.py::start_transaction`).
- 이미지 업로드(`app/products/images.py::save_product_image`)는 프로필 이미지와 동일한 검증
  파이프라인을 쓴다: 5MB 이하 확인 → Pillow로 열어서 `verify()` → 포맷이 JPEG/PNG/WEBP인지
  확인 → 최대 1600px로 리사이즈 → JPEG로 재인코딩해 랜덤 파일명 저장. 최대 5장까지 허용한다.
- **수정/삭제 권한**은 `product.seller_id == current_user.id`(또는 관리자)를 서버에서 매번
  재확인한다. 프론트에서 버튼을 숨기는 것과 무관하게, URL을 직접 조작해서 들어와도 403으로
  막힌다(5.6절 IDOR 대응 참고).
- 거래 이력(`Transaction`)이 하나라도 있는 상품은 삭제를 막는다. FK에 `ON DELETE CASCADE`가
  없는 SQLite 특성상, 상품을 지우면 거래 레코드가 고아 데이터로 남기 때문이다.
- 관리자가 타인의 상품을 삭제하면 `AdminLog`에 자동으로 기록한다.

#### 상품 조회 / 상세 / 검색 (`/products/`, `/products/<id>`)

- 검색은 `Product.title.ilike(f"%{q}%")` 형태로 **파라미터 바인딩된** `LIKE` 쿼리를 쓴다.
  검색어를 SQL 문자열에 직접 이어붙이지 않으므로 `' OR '1'='1` 같은 페이로드를 넣어도 그냥
  "검색 결과 없음"으로 처리된다(문자열 자체가 바인딩 파라미터로만 취급됨).
- 카테고리 필터는 사용자가 임의 문자열을 보내도 서버가 정의한 화이트리스트에 있는 값만
  실제 필터 조건으로 사용한다.
- 차단된(`status=blocked`) 상품은 목록/검색 어디에도 나오지 않으며, 상세페이지 직접 접근 시
  작성자 본인·관리자가 아니면 404로 응답해 "존재 자체를 모르게" 처리한다.
- **조회수**는 접속할 때마다(본인 상품 제외) 무조건 증가한다. 초기에는 세션에 조회한 상품 id를
  기록해 같은 사용자의 중복 조회를 막는 방식이었으나, 요구사항 재검토 후 이 제한을 제거하고
  새로고침해도 계속 올라가도록 변경했다(어뷰징 방지보다 실제 조회 트래픽을 그대로 반영하는
  쪽을 택함).

#### 찜 기능 (`/products/<id>/wish`, `/products/wishlist`)

`Wish` 모델에 `(user_id, product_id)` 유니크 제약을 걸고, 토글 방식(있으면 삭제, 없으면 추가)
으로 처리한다.

#### 상품 카테고리 / 상품 상태

둘 다 `SelectField` + 서버 정의 `CHOICES` 목록으로 제한해, 클라이언트가 스키마에 없는 임의
값을 주입하지 못하게 했다(데이터 무결성 관점).

---

### 5.3 채팅 (1:1 / 전체채팅)

두 채팅 기능 모두 **롱폴링(long polling)** 방식으로 구현했다. 클라이언트가 `GET .../poll?after_id=N`
을 요청하면, 서버는 최대 25초(`LONG_POLL_TIMEOUT_SECONDS`) 동안 1초 간격으로 새 메시지가
있는지 확인하다가, 있으면 즉시 응답하고 없으면 빈 배열을 반환한다. 클라이언트는 응답을 받는
즉시 다음 폴링을 다시 보내는 식으로 "지속 연결"을 흉내낸다.

```python
while time.time() < deadline:
    db.session.commit()  # 트랜잭션을 매번 끝내야 다른 요청이 커밋한 새 메시지가 바로 보인다
    messages = Message.query.filter(Message.room_id == room_id,
                                     Message.id > after_id).order_by(Message.id.asc()).all()
    if messages:
        return jsonify({"messages": [...]})
    time.sleep(LONG_POLL_INTERVAL_SECONDS)
```

`db.session.commit()`을 매 반복마다 호출하는 이유는, SQLite/SQLAlchemy가 트랜잭션을 열어둔
채로 반복 조회하면 다른 요청(다른 스레드)이 커밋한 새 데이터가 바로 보이지 않을 수 있기
때문이다(트랜잭션 격리 수준 문제). 커밋할 변경사항이 없어도 이 호출 자체는 안전하다.

개발 서버 실행 시 `app.run(threaded=True)`를 켜야 한다. 그래야 한 사용자가 폴링으로 대기하는
동안 다른 사용자의 메시지 전송 요청을 동시에 처리할 수 있다.

**1:1 채팅**: 상품 상세 페이지에서 "채팅하기"를 누르면 `ChatRoom`이 생성(또는 기존 방 재사용)
되고, 이후 그 방의 `buyer_id`/`seller_id`와 요청자가 일치하는지(`is_participant`) 모든 조회/
전송/폴링 라우트에서 재확인한다.

**전체채팅**: 로그인한 모든 사용자가 볼 수 있는 공개 채팅. 최근 50건을 초기 로딩하고, 이후는
폴링으로 갱신한다.

**프론트엔드 XSS 방지**: `app/static/js/chat.js`는 메시지를 DOM에 넣을 때 `innerHTML`을 전혀
쓰지 않고 `textContent`만 사용한다. 서버가 내려주는 메시지 내용에 `<script>` 태그가 있어도
브라우저가 이를 텍스트로만 표시하고 실행하지 않는다. 초기 렌더링(Jinja2)도 자동 이스케이프가
기본값이라 별도 처리 없이 안전하다.

**도배(스팸) 방지**: 정교한 rate limiter는 아니지만, 최근 `MESSAGE_BURST_WINDOW_SECONDS`(10초)
안에 `MESSAGE_BURST_LIMIT`(5)개까지는 자유롭게 보낼 수 있고, 그 이상 보내려 하면 429로
거절한다(1:1/전체채팅 공통, `app/chat/routes.py::_is_sending_too_fast`). 메시지 하나 보낼 때마다
무조건 대기시키는 방식(체감상 너무 답답함)이 아니라, 정상적인 대화 속도는 허용하고 순수한
도배("ㅋㅋㅋㅋㅋㅋㅋㅋ" 연타 같은)만 막는 쪽으로 조정했다.

---

### 5.4 신고와 제재

#### 신고 접수 (`app/reports/routes.py`)

상품 신고(`/reports/product/<id>`)와 사용자 신고(`/reports/user/<id>`) 두 라우트로 나뉜다.
본인 상품/본인 계정은 신고할 수 없고, 같은 대상을 이미 신고했다면 재신고를 막는다(DB
유니크 제약 + 애플리케이션 레벨 사전 확인 이중 방어).

#### 신고 누적 자동 차단/휴면

신고가 접수될 때마다 대상의 `report_count`를 1 증가시키고, 설정된 임계치
(`PRODUCT_REPORT_BLOCK_THRESHOLD` / `USER_REPORT_DORMANT_THRESHOLD`, 둘 다 기본값 5)에
도달하면 상품은 `status=blocked`, 사용자는 `status=dormant`로 자동 전환한다.

휴면 처리된 사용자는:
- 로그인을 시도하면 일반 로그인 실패와 동일한 메시지로 거부된다(계정 상태 추측 방지).
- **이미 로그인해 있던 세션도** 상품 등록/수정, 채팅 시작, 채팅 메시지 전송 같은 주요 액션을
  시도하는 순간 다시 차단된다. 로그인 시점 체크만으로는 세션이 유지되는 동안 상태가 바뀐
  경우를 놓치기 때문에, 액션 시점에 별도 데코레이터(`active_account_required`)로 재검증한다.

---

### 5.5 관리자 기능

#### 대시보드 / 신고 큐 / 감사 로그 (`app/admin/routes.py`)

- 대시보드: 전체 회원 수, 상품 수, 대기중인 신고 수, 차단된 상품 수, 휴면/정지 사용자 수를
  집계해서 보여준다.
- 신고 큐(`/admin/reports`): 상태가 `pending`인 신고를 모아서 보여주고, 신고 유형에 따라
  "차단하기/차단 해제"(상품) 또는 "정지하기/정상화"(사용자) 버튼을 노출한다. 관리자가
  차단/정지 조치를 하면 그 대상에 걸린 다른 pending 신고들도 자동으로 `reviewed`로 정리된다.
  기각(`dismiss`)을 누르면 신고를 `dismissed`로 바꾸고 대상의 `report_count`를 1 감소시켜
  자동 차단 임계치 계산에서 빠지게 한다.
- 감사 로그(`/admin/logs`): 관리자가 수행한 모든 조치(`product_block`, `product_unblock`,
  `user_ban`, `user_unban`, `report_dismiss`, `product_delete`)를 최신순으로 보여준다.
  수정/삭제 API를 아예 만들지 않아 append-only를 강제했다.

#### 관리자 지정

회원가입 화면에서 관리자를 만드는 경로는 없다. 대신 Flask CLI 명령을 추가했다:

```bash
export FLASK_APP=run.py
flask make-admin <아이디>
```

#### 권한 검증 (`app/utils/decorators.py::admin_required`)

관리자 라우트는 `@admin_required` 데코레이터로 보호한다. 단순히 `current_user.is_admin()`을
믿지 않고, **매 요청마다 DB에서 `role` 컬럼을 다시 조회**한다. 그 이유는 6절에서 설명한다.

---

### 5.6 거래와 결제 (Mock Payment)

#### 거래 흐름

1. 구매자가 상품 상세에서 "구매하기" → `POST /transactions/start/<product_id>`
   - 본인 상품 구매 불가, 판매중(`selling`) 상태가 아니면 거부, 차단 관계면 거부.
   - **금액은 서버가 `product.price`로 직접 채운다.** 클라이언트가 보낸 `amount` 파라미터는
     애초에 읽지도 않으므로 결제 금액 조작이 불가능하다.
2. 결제 페이지(`/transactions/<id>/pay`)에서 Mock 카드 정보 입력 → `mock_gateway.charge()` 호출.
3. 승인되면 `Transaction.status = paid`, `Product.status = reserved`.
4. 판매자가 "거래 시작(직거래 진행)" → `in_progress` (판매자만 가능).
5. 구매자가 "거래 완료 확정" → `completed`, `Product.status = sold` (구매자만 가능).
6. 완료 후 양측이 후기 작성 가능(거래당 1인 1회).

상태 전이는 `Transaction.can_transition_to()`가 클래스 변수 `ALLOWED_TRANSITIONS` 딕셔너리를
기준으로 검사한다. 클라이언트가 `target_status=completed`를 `pending` 상태에서 바로 보내는
식으로 단계를 건너뛰려 하면 거부된다. 또한 상태 전이 라우트(`/transactions/<id>/transition`)
안에서 "판매자만 `in_progress`로 바꿀 수 있다", "구매자만 `completed`로 바꿀 수 있다"는 역할
기반 제약도 별도로 검사한다.

#### Mock Payment Gateway (`app/payments/mock_gateway.py`)

원래는 Visa/Mastercard 같은 실제 카드사 API나 토스페이먼츠·이니시스 같은 PG(결제대행)사
API 연동을 고려했다. 하지만 개인/학습 프로젝트 범위에서는:

- 카드사/PG API는 사업자 등록 + 가맹점 계약 + 심사를 거쳐야 키가 발급되는 구조라 개인이
  접근하기 어렵다.
- 카드번호 같은 민감정보를 직접 다루려면 PCI-DSS 같은 카드정보 보안 표준을 지켜야 하는데,
  이를 제대로 구현하는 것은 이번 과제 범위를 벗어난다.
- 설령 테스트 키가 있어도 계약/심사 절차를 학기 일정 안에 밟기는 비현실적이다.

그래서 실제 카드사와 통신하지 않고 서버 내부에서 승인/거절을 흉내내는 **Mock Payment
Gateway**로 대체했다. 다만 구조(요청 → 승인 처리 → 거래번호 발급)는 실제 PG 연동 흐름과
비슷하게 맞춰서, 나중에 실제 API로 교체하기 쉽게 만들었다. 테스트 편의를 위해 카드번호가
`0000`으로 끝나면 의도적으로 거절되도록 만들어 결제 실패 케이스도 검증 가능하게 했다.

실제 서비스(당근페이 등)는 보통 PG사에 결제를 위임하는 구조를 쓴다. 카드 원본 번호는 PG사
서버에만 존재하고(토큰화), 가맹점 서버는 토큰과 승인 결과만 받는다. 이 Mock Gateway도 그
원칙만은 실제처럼 지킨다: **카드번호는 `charge()` 함수 안에서만 잠깐 쓰이고, 어디에도 저장되지
않는다.** `Transaction` 테이블에도 카드 관련 필드는 없고 `mock_payment_id`(가상 거래번호)만
저장한다.

#### 거래 내역 / 후기

`/transactions/`에서 내가 구매자 또는 판매자로 참여한 모든 거래를 최신순으로 볼 수 있다.
거래가 `completed` 상태일 때만 후기 작성이 가능하며, 작성 즉시 상대방의 매너온도가
재계산된다.

---

## 6. 보안 요구사항 대응 상세

과제에서 반드시 다루도록 요구한 8개 취약점 항목에 대한 대응을 정리한다.

### 6.1 SQL Injection

**대응**: 모든 DB 접근을 SQLAlchemy ORM으로만 수행하고, 문자열을 조립해 쿼리를 만드는
코드는 프로젝트 전체에 없다. 검색 기능처럼 사용자 입력을 `LIKE` 조건에 쓰는 경우도
`Product.title.ilike(f"%{q}%")`처럼 **파이썬 문자열은 와일드카드 패턴을 만드는 데만 쓰이고,
실제 SQL 전달은 SQLAlchemy가 파라미터 바인딩으로 처리**한다.

**검증**: `tests/test_products.py::test_search_with_sql_injection_style_input_is_safe`가
`아이핀' OR '1'='1` 형태의 페이로드를 검색어로 넣어도 전체 상품이 노출되지 않는지 확인한다.

### 6.2 XSS

**대응**:
- Jinja2 템플릿은 기본적으로 자동 이스케이프를 적용한다. 상품 설명, 신고 사유, 후기 내용
  등 사용자 입력을 그대로 `{{ }}`로 출력하되 `|safe` 필터는 어디에서도 쓰지 않는다.
- 채팅은 서버 렌더링(초기 로드)과 JS 동적 렌더링(폴링 결과)이 섞여 있는데, JS 쪽은
  `innerHTML` 대신 `textContent`만 사용해 DOM 기반 XSS를 원천 차단했다.

**검증**: `tests/test_chat.py::test_message_xss_payload_is_escaped_on_render`가
`<script>alert(1)</script>`를 메시지로 보낸 뒤 렌더링 결과에 스크립트 태그가 그대로 남지
않고 `&lt;script&gt;`로 이스케이프됐는지 확인한다.

### 6.3 CSRF

**대응**: `Flask-WTF`의 `CSRFProtect`를 앱 전역에 적용했다. WTForms로 만든 폼은
`{{ form.hidden_tag() }}`가 토큰을 자동으로 심어주고, WTForms를 쓰지 않는 수동 폼(신고 처리
버튼, 삭제 버튼 등)에는 `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`를
직접 넣는다. JS `fetch()`로 보내는 채팅 메시지 전송은 `<meta name="csrf-token">` 태그에서
토큰을 읽어 `X-CSRFToken` 헤더에 실어 보낸다.

**검증**: `tests/test_csrf.py`는 다른 테스트와 달리 CSRF 보호를 실제로 켠 상태로 앱을 띄워서,
토큰 없이 보낸 POST가 400으로 거부되고 올바른 토큰을 넣으면 통과하는지 확인한다.

### 6.4 IDOR (Insecure Direct Object Reference)

**대응**: id 파라미터로 접근하는 모든 리소스에 대해 "이 리소스가 정말 요청자 것인가"를
서버에서 재확인한다.

| 위치 | 검증 방식 |
|---|---|
| 상품 수정/삭제 | `product.seller_id == current_user.id` (또는 관리자) |
| 상품 이미지 삭제 | 이미지의 `product_id`가 실제로 그 상품 소속인지까지 재확인 |
| 채팅방 조회/전송/폴링 | `room.is_participant(current_user.id)` |
| 거래 상세/결제/상태전이 | `current_user.id in (tx.buyer_id, tx.seller_id)` |
| 마이페이지/거래내역 | 쿼리 자체를 `current_user.id` 기준으로만 필터링 (파라미터로 다른 id를 받지 않음) |

**검증**: `tests/test_products.py`, `tests/test_chat.py`, `tests/test_transactions.py`에
각각 "제3자가 남의 리소스에 접근하면 403"을 확인하는 테스트가 있다. 특히 거래/상품
테스트는 **유효한 CSRF 토큰을 가진 상태에서도** 소유자가 아니면 차단되는지까지 확인해,
CSRF 방어와 IDOR 방어가 서로 다른 계층이라는 점을 명확히 검증한다.

### 6.5 Broken Access Control

**대응**: 관리자 전용 라우트는 `@admin_required` 데코레이터로 보호한다. 개발 중 발견한
문제인데, `current_user.is_admin()`처럼 세션에 로드된 사용자 객체의 속성을 그대로 믿으면
**SQLAlchemy 세션의 identity map 캐시 때문에, 관리자가 방금 권한을 회수해도 그 사용자의
세션에는 옛 권한이 남아있을 수 있는 위험**이 있었다. 그래서 권한/상태 체크가 필요한 지점은
`current_user`의 캐시된 속성을 쓰지 않고, **매 요청마다 필요한 컬럼만 DB에서 새로 조회**하도록
바꿨다.

```python
def is_admin_user(user_id: int) -> bool:
    return db.session.query(User.role).filter_by(id=user_id).scalar() == UserRole.ADMIN
```

이 패턴을 `admin_required`, `active_account_required` 데코레이터와 상품 삭제 권한 체크에
동일하게 적용했다. (자세한 경위는 8절 참고)

**검증**: `tests/test_reports_admin.py::test_non_admin_cannot_access_admin_dashboard`,
`test_admin_can_access_dashboard`가 각각 일반 유저는 403, 관리자는 200을 받는지 확인한다.

### 6.6 파일 업로드 취약점

**대응**: 상품 이미지와 프로필 이미지 모두 동일한 원칙을 따른다.

1. 확장자나 `Content-Type` 헤더를 신뢰하지 않는다(둘 다 클라이언트가 조작 가능).
2. 파일을 Pillow로 실제로 열어보고(`Image.open().verify()`) 진짜 이미지 구조인지 확인한다.
3. 허용 포맷(JPEG/PNG/WEBP)인지 다시 확인한다.
4. **픽셀 데이터를 다시 그려서(재인코딩) 저장**한다. 이 과정에서 파일에 숨어있을 수 있는
   스크립트/폴리글랏 페이로드가 대부분 제거된다.
5. 원본 파일명을 쓰지 않고 서버가 생성한 랜덤 파일명(`uuid4().hex`)으로 저장해 경로 조작이나
   실행 파일 위장 업로드를 막는다.
6. 파일 크기(5MB), 개수(상품당 최대 5장)를 제한한다.

**검증**: `tests/test_products.py::test_fake_file_disguised_as_image_is_rejected`가
`.jpg` 확장자를 붙인 일반 텍스트 파일 업로드를 시도해 "올바른 이미지 파일이 아닙니다"로
거부되는지 확인한다. 프로필 이미지도 수동 curl 테스트로 동일하게 검증했다.

### 6.7 세션 취약점

**대응**:
- 세션 쿠키에 `HttpOnly`(JS로 접근 불가), `SameSite=Lax`, `Secure`(운영 환경에서 활성화)를
  설정했다.
- 로그인 성공 시 `session.clear()` 후 새 세션을 발급해 세션 고정(session fixation) 공격을
  막는다.
- 비밀번호 변경 성공 시에도 세션을 초기화하고 재로그인을 요구한다.
- 로그인 5회 실패 시 15분 계정 잠금으로 무차별 대입(brute-force)을 완화한다.
- `PERMANENT_SESSION_LIFETIME`으로 세션 만료 시간을 설정했다.

**한계**: 현재 세션은 클라이언트 서명 쿠키 방식이라, "다른 기기에 남아있는 세션까지 강제로
끊는" 기능은 서버사이드 세션 저장소(예: Redis) + 세션 버전 토큰이 추가로 필요하다. 이번
범위에서는 구현하지 않고 한계로 남겼다(9절 참고).

### 6.8 개인정보 보호

**대응**:
- 비밀번호는 bcrypt로 해시해서만 저장한다(`tests/test_auth.py::test_password_is_hashed_not_stored_plaintext`
  로 검증).
- 카드번호 등 결제 정보는 Mock Gateway의 `charge()` 함수 안에서만 잠깐 존재하고 어디에도
  저장하지 않는다.
- 공개 프로필은 화이트리스트 방식으로 필요한 필드만 노출하고, 이메일·로그인 실패 이력 같은
  내부 정보는 응답에 포함하지 않는다.
- 회원 탈퇴/소프트 삭제, 개인정보 암호화 저장 등은 이번 범위에서 다루지 않았다(9절 참고).

### 6.9 계정 열거(User Enumeration) 방지

**문제**: 로그인 실패 메시지는 원래 "아이디/비밀번호가 틀림"과 "계정이 잠김"을 서로 다른
문구로 안내하고 있었다. 존재하지 않는 아이디는 절대 잠기지 않으므로, 같은 아이디로 6번
이상 틀리게 로그인해서 응답 문구가 "잠겼습니다"로 바뀌는지만 관찰해도 그 아이디가 실제
존재하는 계정인지 외부에서 추측할 수 있는 사이드채널이었다.

**대응**: 계정이 없을 때/비밀번호가 틀렸을 때/잠겼을 때 모두 완전히 동일한 문구
("아이디 또는 비밀번호가 올바르지 않습니다.")로 응답하도록 통일했다
(`tests/test_security_misc.py::test_nonexistent_username_always_shows_generic_error`,
`test_locked_real_account_shows_identical_generic_error`).

---

## 7. API 엔드포인트 전체 목록

| Method | URL | 설명 | 인증 필요 |
|---|---|---|---|
| GET | `/` | 홈 → 상품 목록으로 리다이렉트 | - |
| GET/POST | `/auth/register` | 회원가입 | - |
| GET/POST | `/auth/login` | 로그인 | - |
| GET | `/auth/logout` | 로그아웃 | ✅ |
| GET/POST | `/auth/password` | 비밀번호 변경 | ✅ |
| GET | `/products/` | 상품 목록/검색 | - |
| GET/POST | `/products/new` | 상품 등록 | ✅ |
| GET | `/products/<id>` | 상품 상세 | - |
| GET/POST | `/products/<id>/edit` | 상품 수정 | ✅ (소유자) |
| POST | `/products/<id>/delete` | 상품 삭제 | ✅ (소유자/관리자) |
| POST | `/products/<id>/images/<image_id>/delete` | 상품 이미지 삭제 | ✅ (소유자) |
| POST | `/products/<id>/wish` | 찜 토글 | ✅ |
| GET | `/products/wishlist` | 찜 목록 | ✅ |
| GET | `/chat/rooms` | 내 1:1 채팅방 목록 | ✅ |
| POST | `/chat/start/<product_id>` | 채팅방 시작 | ✅ |
| GET | `/chat/rooms/<id>` | 채팅방 상세 | ✅ (참여자) |
| POST | `/chat/rooms/<id>/messages` | 메시지 전송 | ✅ (참여자) |
| GET | `/chat/rooms/<id>/poll` | 롱폴링 | ✅ (참여자) |
| GET | `/chat/global` | 전체채팅 | ✅ |
| POST | `/chat/global/messages` | 전체채팅 전송 | ✅ |
| GET | `/chat/global/poll` | 전체채팅 롱폴링 | ✅ |
| GET/POST | `/reports/product/<id>` | 상품 신고 | ✅ |
| GET/POST | `/reports/user/<id>` | 사용자 신고 | ✅ |
| GET | `/admin/` | 관리자 대시보드 | ✅ (관리자) |
| GET | `/admin/reports` | 신고 큐 | ✅ (관리자) |
| POST | `/admin/reports/<id>/dismiss` | 신고 기각 | ✅ (관리자) |
| POST | `/admin/products/<id>/block` `/unblock` | 상품 수동 차단/해제 | ✅ (관리자) |
| POST | `/admin/users/<id>/ban` `/unban` | 사용자 정지/정상화 | ✅ (관리자) |
| GET | `/admin/logs` | 감사 로그 | ✅ (관리자) |
| GET | `/users/<id>` | 공개 프로필 | - |
| POST | `/users/<id>/block` `/unblock` | 사용자 차단/해제 | ✅ |
| GET | `/users/me/blocked` | 차단 목록 | ✅ |
| POST | `/transactions/start/<product_id>` | 거래 시작 | ✅ |
| GET/POST | `/transactions/<id>/pay` | Mock 결제 | ✅ (구매자) |
| GET | `/transactions/<id>` | 거래 상세 | ✅ (당사자) |
| POST | `/transactions/<id>/transition` | 상태 전이 | ✅ (당사자, 역할별 제한) |
| GET/POST | `/transactions/<id>/review` | 후기 작성 | ✅ (당사자) |
| GET | `/transactions/` | 거래 내역 | ✅ |
| GET | `/mypage/` | 마이페이지 대시보드 | ✅ |
| GET/POST | `/mypage/profile-image` | 프로필 이미지 업로드 | ✅ |
| POST | `/mypage/profile-image/delete` | 프로필 이미지 삭제 | ✅ |

---

## 8. 테스트

### 8.1 구성

`pytest` + Flask 기본 테스트 클라이언트를 사용했다. `tests/conftest.py`의 `app` fixture가
테스트마다 **임시 디렉토리에 새 SQLite 파일**을 만들어 앱을 초기화하므로, 테스트 간 데이터가
서로 섞이지 않는다(인메모리 SQLite 대신 파일 기반을 택한 이유는 Flask-SQLAlchemy의 세션
스코프 문제로 인메모리 DB가 커넥션마다 초기화되는 걸 피하기 위함이다). 대부분의 테스트는
`WTF_CSRF_ENABLED = False`로 CSRF를 꺼서 비즈니스 로직/권한 로직에 집중하고,
`tests/test_csrf.py`만 별도 fixture로 CSRF를 켠 채 검증한다.

### 8.2 테스트 목록 (57개)

| 파일 | 개수 | 주요 검증 내용 |
|---|---|---|
| `test_auth.py` | 8 | 회원가입/로그인, 계정 열거 방지, 로그인 잠금, 비밀번호 해시, 비밀번호 변경 재인증 |
| `test_products.py` | 13 | 로그인 필수, 위장 파일 업로드 차단, SQL Injection 무력화, IDOR(수정/삭제), 차단 상품 노출 제한, 무료나눔(0원) 등록, 디코딩 폭탄 방어, jpg/jpeg 확장자 |
| `test_reports_admin.py` | 8 | 신고 누적 자동 차단/휴면, 중복 신고 방지, 관리자 권한(403/200), 관리자 조치 시 신고 자동 처리 |
| `test_chat.py` | 9 | 채팅방 IDOR(조회/전송/폴링), 메시지 XSS 이스케이프, 차단 사용자와 채팅 불가, 전체채팅 필터링, 도배 방지 쿨다운 |
| `test_transactions.py` | 15 | 결제 거절, 금액 조작 방지, 거래 IDOR, 역할 기반 상태 전이(역전 방지 포함), 리뷰 IDOR·완료 전 차단, 중복 후기 방지, 매너온도 클램프, 거래 이력 상품 삭제 보호 |
| `test_csrf.py` | 5 | CSRF 토큰 없는 요청 차단(회원가입/1:1채팅/전체채팅), 유효한 토큰(폼/헤더)으로는 통과 |
| `test_seed.py` | 2 | 데모 데이터가 예상한 개수대로 생성되는지, 재실행해도 중복 생성되지 않는지(idempotent) |
| `test_security_misc.py` | 10 | 위시리스트 IDOR, 관리자 개별 라우트(reports/logs/dismiss) 접근 제어, 세션 재발급, 쿠키 속성(HttpOnly/SameSite), 로그인 실패 메시지 통일(계정 열거 방지) |

### 8.3 실행 방법

```bash
pip install -r requirements-dev.txt
pytest -v
```

### 8.4 이번 라운드에서 추가/보완한 항목

지난 코드 리뷰에서 발견한 항목들을 반영했다. 상세 결과는 `test-checklist.md` 참고.

- **CSRF**: `/chat/rooms/<id>/messages`, `/chat/global/messages`에 대한 차단/통과 테스트 추가
- **디코딩 폭탄**: 실제로는 Pillow가 `Image.open()` 시점에 이미 `DecompressionBombError`를
  던지고 있어서(기존 try/except 안에서 처리됨) 취약점이 아니었음을 확인. 방어 코드는 한 겹
  더 명시적으로 추가(6.9절 정정 참고)
- **리뷰 IDOR / 완료 전 접근**: 기존 코드가 이미 올바르게 막고 있었고, 테스트로 고정
- **위시리스트 IDOR**: `(user_id, product_id)` 기준으로만 동작해 원래 안전했음을 테스트로 확인
- **관리자 개별 라우트**: `/admin/reports`, `/admin/logs`, `/admin/reports/<id>/dismiss` 각각
  비관리자 접근 차단 테스트 추가
- **세션 재발급/로그아웃 무효화**: 로그인 라우트의 `session.clear()`가 실제로 쿠키 값을
  바꾸는지, 로그아웃 후 보호 페이지 접근이 막히는지 테스트로 고정
- **쿠키 속성**: `Set-Cookie`에 `HttpOnly`/`SameSite=Lax` 포함 여부 테스트
- **로그인 실패 메시지 계정 열거**: 실제로 존재하는 버그였음(6.9절) — 잠금 메시지를 일반
  오류 메시지와 통일해서 수정
- **매너온도 클램프**: 실제 평점(1~5점)만으로는 공식상 0/99 경계에 도달할 수 없다는 것을
  확인하고 문서화, 클램프 로직 자체는 상수를 조정한 별도 테스트로 검증

---

## 9. 실행 방법

### 9.0 최초 1회 설정

**macOS / Linux (bash/zsh)**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # SECRET_KEY는 실제 랜덤 값으로 교체
```

**Windows (PowerShell)**
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env              # SECRET_KEY는 실제 랜덤 값으로 교체
```
> PowerShell에서는 `source`가 아니라 `.\venv\Scripts\Activate.ps1`을 쓴다(`source`는 bash/zsh 전용
> 명령이라 PowerShell에는 없다). 만약 "이 시스템에서 스크립트 실행이 금지되어 있습니다" 같은
> 실행 정책 오류가 나면 관리자 권한 PowerShell에서
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 한 번 실행 후 다시 시도한다.
> cmd.exe를 쓴다면 `venv\Scripts\activate.bat`을 대신 쓴다.

### 9.1 서버 실행 (매번 반복)

```bash
python run.py        # Windows는 python 대신 py run.py 도 동일하게 동작
```

`http://127.0.0.1:5000` 접속. 첫 실행 시 `instance/app.db`가 자동 생성된다.

### 9.2 관리자 계정 지정

```bash
export FLASK_APP=run.py     # Windows PowerShell: $env:FLASK_APP = "run.py"
flask make-admin <가입한 아이디>
```

### 9.3 문제 해결 — `sqlite3.OperationalError: unable to open database file`

**원인**: `.env`의 `DATABASE_URL=sqlite:///instance/app.db`처럼 **상대경로**를 직접 넣으면,
`config.py`가 원래 갖고 있던 안전한 기본값(실행 시점에 `os.path.dirname(__file__)`로 자동
계산되는 절대경로)을 덮어써버린다. 이 상대경로는 특정 Windows 환경에서 sqlite가 파일을 여는
데 실패하는 원인이 됐다(폴더 권한, sqlite3/SQLAlchemy 단독 테스트는 전부 정상이었는데도
Flask 앱 안에서만 재현되는 게 그 증거).

**조치**: `.env`에는 `DATABASE_URL` 줄을 아예 넣지 않는다. 비워두면 `config.py`의 동적 절대경로
기본값이 자동으로 쓰이고, 이건 하드코딩이 아니라 실행되는 컴퓨터/폴더 기준으로 매번 새로
계산되는 값이라 **채점 환경 등 다른 컴퓨터에서 실행해도 항상 정확하게 동작**한다(이식성 문제
없음). sqlite가 아닌 다른 DB(운영 환경의 Postgres 등)를 쓸 때만 `.env.example`의 주석을 참고해서
`DATABASE_URL`을 채운다.

부수적으로, `.env` 파일이 실제로는 로드되지 않고 있던 문제도 함께 고쳤다(`requirements.txt`에
`python-dotenv`가 있었지만 `load_dotenv()`를 호출하는 코드가 없어서, `.env`를 바꿔도 아무 효과가
없었다). 이제 `run.py`가 시작할 때 `.env`를 실제로 읽어 환경변수에 반영한다.

### 9.4 데모 데이터 시딩

빈 화면 대신 실제 운영중인 서비스처럼 보이도록, 예시 데이터를 한 번에 채워 넣는 CLI 명령을
만들어뒀다.

```bash
export FLASK_APP=run.py
flask seed-demo
```

`app/seed.py`가 실행되며, 이미 사용자 데이터가 하나라도 있으면 아무것도 하지 않고
건너뛴다(중복 실행 방지). 처음부터 다시 만들고 싶으면 `instance/app.db`를 지우고
`db.create_all()`을 다시 실행한 뒤 시딩하면 된다.

**생성되는 데이터**

| 항목 | 내용 |
|---|---|
| 사용자 | 8명 (관리자 1명 `minji_kim` 포함). 프로필 사진이 있는 사용자도 일부 포함 |
| 상품 | 16개. 카테고리·상태(판매중/예약중/거래완료/차단됨)가 골고루 섞여 있고, 카테고리별 색상의 플레이스홀더 이미지가 자동 생성됨 |
| 찜 | 6건 |
| 1:1 채팅 | 2개 방, 실제 대화 흐름을 흉내낸 메시지 포함 |
| 전체채팅 | 5건 |
| 거래 | 3건 — 완료(후기 2건 포함, 매너온도 반영됨) / 진행중 / 결제완료(직거래 대기) 각 1건씩 |
| 신고 | 상품 신고 5건(자동 차단 임계치 도달 → 상품이 실제로 `blocked` 상태), 사용자 신고 1건(아직 대기중 → 관리자 신고 큐에서 확인 가능) |
| 사용자 차단 | 1건 |
| 관리자 로그 | 1건 |

**로그인 정보**: 모든 데모 계정의 비밀번호는 `abcd1234`이다.

| 아이디 | 닉네임 | 역할 |
|---|---|---|
| `minji_kim` | 민지 | 관리자 |
| `junho_lee` | 준호 | 일반 사용자 |
| `seoyeon_p` | 서연 | 일반 사용자 |
| `hyunwoo_c` | 현우 | 일반 사용자 |
| `yuna_jung` | 유나 | 일반 사용자 |
| `dongho_kim` | 동호 | 일반 사용자 |
| `sujin_han` | 수진 | 일반 사용자 |
| `noisy_guy` | 시끄러운사람 | 일반 사용자 (신고/차단 데모 대상) |

---

## 10. 알려진 한계 및 향후 개선 과제

개발 과정에서 의도적으로 범위를 좁히거나, 시간 관계상 다음 단계로 미룬 부분을 정리한다.
우선순위와 이유는 채팅으로 별도 전달한 목록을 참고.

1. **결제 idempotency key 미사용** — `Transaction.idempotency_key` 컬럼은 있지만, 실제로
   중복 결제 요청을 막는 검증 로직이 붙어있지 않다.
2. **이메일 인증 없음** — 회원가입 시 입력한 이메일이 실제로 본인 소유인지 확인하지 않는다.
3. **다른 기기 세션 강제 로그아웃 미구현** — 서버사이드 세션 저장소가 필요하다.
4. **신고 어뷰징(조직적 신고) 방지 없음** — 신고자 다양성(같은 IP/계정 몰림 여부)을 고려하지
   않고 단순 누적 횟수만 본다.
5. **Rate limiting이 로그인 실패 잠금 + 채팅 쿨다운 정도만 존재** — 회원가입 남발, 신고
   남발 방지는 아직 없다. (채팅 도배는 5.3절 참고 — 10초에 5개 버스트 허용 후 차단)
6. **Flask-Migrate 버전 관리 마이그레이션 미사용** — 현재는 `db.create_all()`만 쓰고 있어,
   운영 환경에서 스키마를 바꾸려면 별도 마이그레이션 스크립트 작성이 필요하다.
7. **CSP가 `style-src`에 `'unsafe-inline'`을 허용** — 인라인 스타일을 정리하면 더 엄격한
   CSP를 적용할 수 있다.
8. **관리자용 전체 회원/상품/거래 관리 페이지 없음** — 지금은 신고 큐를 거쳐야만 제재할 수
   있고, 신고되지 않은 대상을 관리자가 임의로 찾아서 조치하거나 거래 내역을 직접 들여다보는
   화면은 없다. (과제 최소 요구사항인 "관리자가 신고·유저·상품을 관리"는 이미 충족하며,
   거래 전용 관리 화면은 시간 대비 우선순위가 낮다고 판단해 이번 범위에서는 만들지 않았다.)
9. **채팅 욕설 필터링 없음** — 도배(속도) 방지는 추가했지만 비속어 필터링은 없다.
10. **프로덕션 배포 설정 미흡** — `SESSION_COOKIE_SECURE=True`, HTTPS, `debug=False`, WSGI
    서버(gunicorn 등)로의 교체가 필요하다.
11. ~~이미지 디코딩 폭탄(decompression bomb) 방어 미흡~~ — **정정**: 처음엔 `verify()` 이후의
    두 번째 `Image.open()`+`thumbnail()` 호출이 try/except 밖에 있어 취약하다고 판단했으나,
    실제로 Pillow는 `Image.open()` 시점에 곧바로 `DecompressionBombError`를 던진다는 것을
    직접 테스트로 확인했다(즉 이미 있던 첫 번째 try/except 안에서 걸러지고 있었음). 실제
    취약점은 아니었지만, 방어 코드를 한 겹 더 명시적으로 추가해뒀다.
