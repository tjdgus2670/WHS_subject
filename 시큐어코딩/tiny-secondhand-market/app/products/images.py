import os
import uuid
from io import BytesIO

from flask import current_app
from PIL import Image

MAX_IMAGE_DIMENSION = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGES_PER_PRODUCT = 5
MAX_SINGLE_FILE_BYTES = 5 * 1024 * 1024


class ImageValidationError(Exception):
    """업로드된 파일이 이미지로서 유효하지 않을 때 발생시킨다."""
    pass


def _product_upload_dir() -> str:
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], "products")
    os.makedirs(path, exist_ok=True)
    return path


def save_product_image(file_storage) -> str:
    """업로드된 파일을 검증하고, 서버에서 다시 그려서(재인코딩) 랜덤 파일명으로 저장한다.

    확장자나 Content-Type 헤더는 클라이언트가 얼마든지 조작할 수 있어서 신뢰하지 않는다.
    대신 (1) 실제로 Pillow가 이미지로 열 수 있는지, (2) 허용된 포맷인지 확인하고,
    (3) 픽셀 데이터를 다시 그려서 새 파일로 저장한다. 이 과정에서 파일 안에 숨어있을 수
    있는 스크립트/폴리글랏 페이로드가 대부분 제거된다. 원본 파일명도 사용하지 않고
    서버가 생성한 랜덤 파일명으로 저장해서 경로 조작이나 실행 파일 위장 업로드를 막는다.
    """
    raw = file_storage.read()

    if len(raw) == 0:
        raise ImageValidationError("빈 파일은 업로드할 수 없습니다.")
    if len(raw) > MAX_SINGLE_FILE_BYTES:
        raise ImageValidationError("이미지 하나당 용량은 5MB를 넘을 수 없습니다.")

    try:
        img = Image.open(BytesIO(raw))
        img.verify()  # 실제 이미지 구조가 맞는지 확인 (깨진 파일/위장 파일 여기서 대부분 걸러짐)
    except Exception:
        raise ImageValidationError("올바른 이미지 파일이 아닙니다.")

    # verify() 호출 이후에는 파일 객체를 다시 열어야 픽셀 데이터에 접근할 수 있다.
    # 실제 픽셀 디코딩(convert/thumbnail)이 일어나는 아래 블록에서 디코딩 폭탄
    # (용량은 작지만 선언된 해상도가 극단적으로 큰 이미지)이 Pillow의
    # DecompressionBombError로 이어질 수 있어 이 블록도 반드시 try/except로 감싼다.
    try:
        img = Image.open(BytesIO(raw))

        if img.format not in ALLOWED_FORMATS:
            raise ImageValidationError("JPEG, PNG, WEBP 형식만 업로드할 수 있습니다.")

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    except ImageValidationError:
        raise
    except Exception:
        raise ImageValidationError("이미지 해상도가 너무 크거나 처리할 수 없는 파일입니다.")

    filename = f"{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(_product_upload_dir(), filename)
    img.save(save_path, format="JPEG", quality=85)

    return filename


def delete_product_image_file(filename: str) -> None:
    path = os.path.join(_product_upload_dir(), filename)
    if os.path.exists(path):
        os.remove(path)
