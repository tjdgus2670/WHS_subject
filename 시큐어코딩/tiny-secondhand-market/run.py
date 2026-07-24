from dotenv import load_dotenv

load_dotenv()  # .env 파일의 SECRET_KEY 등을 실제로 환경변수에 반영한다.
# (이 호출이 없으면 .env 파일을 만들어도 아무 효과가 없고 config.py의 기본값만 쓰인다.)
# 주의: .env에 DATABASE_URL을 상대경로로 넣으면 안 된다 - .env.example의 주석 참고.

from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # 개발 편의용. 스키마 변경이 생기면 Flask-Migrate로 전환할 예정.
    # threaded=True 필수: 롱폴링 요청이 최대 25초까지 붙잡고 있는 동안
    # 다른 사용자의 요청(메시지 전송 등)이 동시에 처리되어야 하기 때문.
    app.run(debug=True, threaded=True)
