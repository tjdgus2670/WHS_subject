import os
import uuid
from io import BytesIO

from flask import current_app
from PIL import Image, ImageOps

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_FILE_BYTES = 5 * 1024 * 1024
AVATAR_SIZE = 400


class ImageValidationError(Exception):
    pass


def _profile_upload_dir() -> str:
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], "profiles")
    os.makedirs(path, exist_ok=True)
    return path


def save_profile_image(file_storage) -> str:
    """프로필 이미지도 상품 이미지(app/products/images.py)와 동일한 원칙으로 검증한다:
    확장자/Content-Type을 믿지 않고 실제로 Pillow가 열 수 있는 이미지인지 확인한 뒤,
    정사각형으로 잘라 재인코딩해서 랜덤 파일명으로 저장한다."""
    raw = file_storage.read()

    if len(raw) == 0:
        raise ImageValidationError("빈 파일은 업로드할 수 없습니다.")
    if len(raw) > MAX_FILE_BYTES:
        raise ImageValidationError("이미지 용량은 5MB를 넘을 수 없습니다.")

    try:
        img = Image.open(BytesIO(raw))
        img.verify()
    except Exception:
        raise ImageValidationError("올바른 이미지 파일이 아닙니다.")

    try:
        img = Image.open(BytesIO(raw))
        if img.format not in ALLOWED_FORMATS:
            raise ImageValidationError("JPEG, PNG, WEBP 형식만 업로드할 수 있습니다.")

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # 정사각형으로 중앙 크롭 후 아바타 크기로 축소 (업로드한 이미지 비율이 어떻든 일관된 원형 아바타로 보이게)
        img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), method=Image.LANCZOS)
    except ImageValidationError:
        raise
    except Exception:
        raise ImageValidationError("이미지 해상도가 너무 크거나 처리할 수 없는 파일입니다.")

    filename = f"{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(_profile_upload_dir(), filename)
    img.save(save_path, format="JPEG", quality=88)

    return filename


def delete_profile_image_file(filename: str) -> None:
    if not filename:
        return
    path = os.path.join(_profile_upload_dir(), filename)
    if os.path.exists(path):
        os.remove(path)
