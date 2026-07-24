from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, NumberRange


class MockPaymentForm(FlaskForm):
    card_number = StringField("카드번호", validators=[
        DataRequired(message="카드번호를 입력해주세요."),
        Regexp(r"^[0-9 ]{13,19}$", message="숫자 13~19자리로 입력해주세요."),
    ])
    expiry = StringField("유효기간(MM/YY)", validators=[
        DataRequired(message="유효기간을 입력해주세요."),
        Regexp(r"^(0[1-9]|1[0-2])\/[0-9]{2}$", message="MM/YY 형식으로 입력해주세요."),
    ])
    cvc = StringField("CVC", validators=[
        DataRequired(message="CVC를 입력해주세요."),
        Regexp(r"^[0-9]{3,4}$", message="CVC는 3~4자리 숫자입니다."),
    ])
    submit = SubmitField("결제하기")


class ReviewForm(FlaskForm):
    rating = IntegerField("별점 (1~5)", validators=[
        DataRequired(message="별점을 입력해주세요."),
        NumberRange(min=1, max=5, message="별점은 1~5 사이여야 합니다."),
    ])
    content = TextAreaField("후기", validators=[Length(max=500)])
    submit = SubmitField("후기 남기기")
