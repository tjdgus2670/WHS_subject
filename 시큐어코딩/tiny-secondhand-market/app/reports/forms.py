from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

REASON_CHOICES = [
    ("fraud", "사기 의심"),
    ("fake_listing", "허위 매물"),
    ("abusive", "욕설/비방"),
    ("inappropriate", "부적절한 게시물"),
    ("etc", "기타"),
]


class ReportForm(FlaskForm):
    reason = SelectField("신고 사유", choices=REASON_CHOICES, validators=[DataRequired()])
    description = TextAreaField("상세 설명 (선택)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("신고하기")
