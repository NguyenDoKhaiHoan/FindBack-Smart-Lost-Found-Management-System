"""Các nghiệp vụ tạo, xem danh sách, sửa, xóa và quyền sở hữu."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from app.modules.posts.models.post import Category, Post
from app.modules.posts.schemas.post import PostCreate, PostUpdate, PostListQuery
from app.modules.posts.services import listings
from app.shared.errors import DomainError


def post_stub(**changes):
    data = dict(id=uuid4(), owner_id=uuid4(), status='OPEN', is_hidden=False,
                deleted_at=None, title='Ví', description='Mất ví', images=[])
    data.update(changes)
    return SimpleNamespace(**data)


def test_create_post_success():
    db = MagicMock()
    db.get.return_value = Category(is_active=True)
    owner_id = uuid4()
    payload = PostCreate(type='LOST', category_id=uuid4(), title='Ví',
                         description='Mất ví', location='Hà Nội',
                         event_time=datetime.now(timezone.utc))
    with patch.object(listings, 'update_search_text'), \
         patch.object(listings.PostResponse, 'model_validate', return_value=object()):
        listings.create_post(db, payload, owner_id)
    saved = db.add.call_args.args[0]
    assert isinstance(saved, Post) and saved.owner_id == owner_id
    db.commit.assert_called_once()


def test_list_posts_success():
    db = MagicMock()
    db.scalar.return_value = 21
    db.scalars.return_value.all.return_value = []
    result = listings.list_posts(db, PostListQuery(page=2, page_size=10))
    assert (result.total, result.total_pages, result.page) == (21, 3, 2)


def test_edit_post_success():
    db, post = MagicMock(), post_stub()
    with patch.object(listings, 'lock_editable_post', return_value=post), \
         patch.object(listings, 'update_search_text'), \
         patch.object(listings.PostResponse, 'model_validate', return_value=object()):
        listings.edit_post(db, post.id, post.owner_id, PostUpdate(title='Ví mới'))
    assert post.title == 'Ví mới'
    db.commit.assert_called_once()


def test_delete_post_success():
    db, post = MagicMock(), post_stub()
    with patch.object(listings, 'lock_editable_post', return_value=post):
        listings.delete_post(db, post.id, post.owner_id)
    assert post.deleted_at is not None
    db.commit.assert_called_once()


@pytest.mark.parametrize('reason', ['missing', 'non_owner'])
def test_edit_or_delete_rejects_invalid_access(reason):
    post = post_stub()
    with patch.object(listings, 'PostRepository') as repo:
        repo.return_value.get_for_update.return_value = None if reason == 'missing' else post
        with pytest.raises(DomainError) as err:
            listings.lock_editable_post(MagicMock(), post.id,
                                        post.owner_id if reason == 'missing' else uuid4())
    expected = 'POST_NOT_FOUND' if reason == 'missing' else 'POST_OWNER_REQUIRED'
    assert err.value.code == expected
