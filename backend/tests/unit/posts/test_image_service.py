"""Ảnh hợp lệ, file lỗi, quá giới hạn, lưu và rollback."""
import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from fastapi import UploadFile
from PIL import Image
from app.modules.posts.services import image_service
from app.shared.errors import DomainError


def png_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (12, 12), 'red').save(buf, format='PNG')
    return buf.getvalue()


def upload():
    return UploadFile(file=io.BytesIO(png_bytes()), filename='photo.png',
                      headers={'content-type': 'image/png'})


def test_valid_image():
    data, mime = image_service.clean_image(png_bytes(), 'image/png')
    assert data and mime == 'image/png'


@pytest.mark.parametrize('data,mime,code', [
    (b'', 'image/png', 'EMPTY_IMAGE'),
    (b'not-image', 'image/png', 'INVALID_IMAGE'),
    (b'x' * (5 * 1024 * 1024 + 1), 'image/png', 'IMAGE_TOO_LARGE'),
])
def test_invalid_image(data, mime, code):
    with pytest.raises(DomainError) as err:
        image_service.clean_image(data, mime)
    assert err.value.code == code


def test_upload_limit(tmp_path):
    db = MagicMock()
    db.scalar.return_value = 5
    with patch.object(image_service, 'lock_editable_post'):
        with pytest.raises(DomainError) as err:
            image_service.upload_image(db, uuid4(), upload(), uuid4(), tmp_path)
    assert err.value.code == 'IMAGE_LIMIT'


def test_upload_success_and_cleanup_on_failure(tmp_path):
    db, post_id = MagicMock(), uuid4()
    db.scalar.return_value = 0
    def assign_generated_fields():
        record = db.add.call_args.args[0]
        record.id = uuid4()
        record.created_at = datetime.now(timezone.utc)
    db.flush.side_effect = assign_generated_fields
    with patch.object(image_service, 'lock_editable_post'):
        result = image_service.upload_image(db, post_id, upload(), uuid4(), tmp_path)
    saved = tmp_path / 'posts' / str(post_id) / str(result.image.id)
    assert saved.is_file()
    db.commit.assert_called_once()

    db2 = MagicMock()
    db2.scalar.return_value = 0
    def assign_fields_second():
        record = db2.add.call_args.args[0]
        record.id = uuid4()
        record.created_at = datetime.now(timezone.utc)
    db2.flush.side_effect = assign_fields_second
    db2.commit.side_effect = RuntimeError('commit failed')
    with patch.object(image_service, 'lock_editable_post'):
        with pytest.raises(RuntimeError, match='commit failed'):
            image_service.upload_image(db2, uuid4(), upload(), uuid4(), tmp_path)
    db2.rollback.assert_called_once()
    assert len(list(tmp_path.rglob('photo.png'))) == 0
    # Chỉ còn ảnh upload thành công; pytest tự dọn tmp_path sau test.
    assert len([p for p in tmp_path.rglob('*') if p.is_file()]) == 1
