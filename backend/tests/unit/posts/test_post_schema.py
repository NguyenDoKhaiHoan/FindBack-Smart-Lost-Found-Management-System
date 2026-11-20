"""Validation đầu vào cho tạo/sửa/liệt kê bài đăng."""
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.modules.posts.schemas.post import PostCreate, PostUpdate, PostListQuery

@pytest.fixture
def payload():
    return dict(type='LOST', category_id=str(uuid4()), title='Mất ví',
                description='Ví màu đen', location='Hà Nội',
                event_time='2026-11-20T08:00:00+07:00')

@pytest.mark.parametrize('kind', ['LOST', 'FOUND'])
def test_create_lost_found(payload, kind):
    payload['type'] = kind
    assert PostCreate.model_validate(payload).type.value == kind

def test_create_invalid_data(payload):
    payload['title'] = '   '
    with pytest.raises(ValidationError):
        PostCreate.model_validate(payload)

def test_create_missing_field(payload):
    payload.pop('location')
    with pytest.raises(ValidationError):
        PostCreate.model_validate(payload)

def test_update_valid_and_invalid():
    assert PostUpdate(title='Tên mới').title == 'Tên mới'
    with pytest.raises(ValidationError):
        PostUpdate.model_validate({})

def test_list_invalid_page():
    with pytest.raises(ValidationError):
        PostListQuery(page=0)
