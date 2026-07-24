from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Email, Regexp, Optional


class RegisterForm(FlaskForm):
    username = StringField("아이디", validators=[
        DataRequired(message="아이디를 입력해주세요."),
        Length(min=4, max=20, message="아이디는 4~20자로 입력해주세요."),
        Regexp(r"^[a-zA-Z0-9_]+$", message="아이디는 영문, 숫자, _만 사용할 수 있습니다."),
    ])
    email = StringField("이메일", validators=[
        DataRequired(message="이메일을 입력해주세요."),
        Email(message="이메일 형식이 올바르지 않습니다."),
        Length(max=120),
    ])
    nickname = StringField("닉네임", validators=[
        DataRequired(message="닉네임을 입력해주세요."),
        Length(min=2, max=20, message="닉네임은 2~20자로 입력해주세요."),
    ])
    region = StringField("동네", validators=[Optional(), Length(max=50)])

    # 비밀번호 정책: 8자 이상 + 영문/숫자 혼합 (최소한의 기준, 필요하면 특수문자 조건 추가 예정)
    password = PasswordField("비밀번호", validators=[
        DataRequired(message="비밀번호를 입력해주세요."),
        Length(min=8, max=64, message="비밀번호는 8자 이상이어야 합니다."),
        Regexp(r"^(?=.*[A-Za-z])(?=.*\d).+$", message="비밀번호는 영문과 숫자를 모두 포함해야 합니다."),
    ])
    password_confirm = PasswordField("비밀번호 확인", validators=[
        DataRequired(),
        EqualTo("password", message="비밀번호가 일치하지 않습니다."),
    ])
    submit = SubmitField("가입하기")


class LoginForm(FlaskForm):
    username = StringField("아이디", validators=[DataRequired(message="아이디를 입력해주세요.")])
    password = PasswordField("비밀번호", validators=[DataRequired(message="비밀번호를 입력해주세요.")])
    submit = SubmitField("로그인")


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField("현재 비밀번호", validators=[DataRequired()])
    new_password = PasswordField("새 비밀번호", validators=[
        DataRequired(),
        Length(min=8, max=64, message="비밀번호는 8자 이상이어야 합니다."),
        Regexp(r"^(?=.*[A-Za-z])(?=.*\d).+$", message="비밀번호는 영문과 숫자를 모두 포함해야 합니다."),
    ])
    new_password_confirm = PasswordField("새 비밀번호 확인", validators=[
        DataRequired(),
        EqualTo("new_password", message="비밀번호가 일치하지 않습니다."),
    ])
    submit = SubmitField("변경하기")
