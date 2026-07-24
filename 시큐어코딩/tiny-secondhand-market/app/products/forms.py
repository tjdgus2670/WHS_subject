from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange

# 카테고리/상태는 클라이언트가 임의 문자열을 보내지 못하게 서버에서 정의한 목록만 허용한다.
CATEGORY_CHOICES = [
    ("electronics", "전자기기"),
    ("clothing", "의류"),
    ("furniture", "가구/인테리어"),
    ("books", "도서"),
    ("beauty", "뷰티/미용"),
    ("sports", "스포츠/레저"),
    ("kids", "유아동"),
    ("etc", "기타"),
]

CONDITION_CHOICES = [
    ("new", "새 상품"),
    ("like_new", "거의 새 것"),
    ("used", "사용감 있음"),
]

SORT_CHOICES = [
    ("latest", "최신순"),
    ("price_asc", "낮은 가격순"),
    ("price_desc", "높은 가격순"),
]


class ProductForm(FlaskForm):
    title = StringField("제목", validators=[
        DataRequired(message="제목을 입력해주세요."),
        Length(min=2, max=100),
    ])
    description = TextAreaField("설명", validators=[
        DataRequired(message="설명을 입력해주세요."),
        Length(min=5, max=2000, message="설명은 5~2000자로 입력해주세요."),
    ])
    # 주의: DataRequired는 값의 진위(bool)로 판단해서 0을 "입력 안 함"으로 취급한다.
    # 무료나눔(가격 0원)을 지원하려면 실제로 필드가 제출됐는지만 보는 InputRequired를 써야 한다.
    price = IntegerField("가격(원)", validators=[
        InputRequired(message="가격을 입력해주세요."),
        NumberRange(min=0, max=100_000_000, message="가격은 0원 이상 1억원 이하로 입력해주세요."),
    ])
    is_free = BooleanField("무료 나눔")
    category = SelectField("카테고리", choices=CATEGORY_CHOICES, validators=[DataRequired()])
    condition = SelectField("상품 상태", choices=CONDITION_CHOICES, validators=[DataRequired()])
    submit = SubmitField("등록하기")
