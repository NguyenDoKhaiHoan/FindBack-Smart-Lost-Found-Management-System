import uuid
import pytest
from app.modules.notifications_admin.services.notification_service import NotificationService
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal
from app.shared.errors import NotFoundError, ValidationError


# ============================================================================
# PRIV-01: Metadata Security Sanitization Unit Tests (8 Required Test Cases)
# ============================================================================

def test_metadata_sanitization_1_valid_metadata():
    """Case 1: Standard approved metadata keys are preserved."""
    data = {
        "post_id": "b3e0cf55-a249-4114-8aa4-b3c0762a4eb1",
        "resource_type": "POST",
        "action": "RESOLVE",
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    assert sanitized["post_id"] == "b3e0cf55-a249-4114-8aa4-b3c0762a4eb1"
    assert sanitized["resource_type"] == "POST"
    assert sanitized["action"] == "RESOLVE"


def test_metadata_sanitization_2_token_at_root():
    """Case 2: Token placed at the root level is stripped."""
    data = {
        "token": "secret_bearer_token_xyz",
        "post_id": "12345",
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    assert "token" not in sanitized
    assert sanitized["post_id"] == "12345"


def test_metadata_sanitization_3_token_in_nested_object():
    """Case 3: Token hidden inside a nested dictionary is stripped."""
    data = {
        "claim_id": {
            "token": "jwt_secret_token",
            "public_reference": "REF-999",
        }
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    assert "token" not in sanitized["claim_id"]
    assert sanitized["claim_id"]["public_reference"] == "REF-999"


def test_metadata_sanitization_4_password_in_nested_array():
    """Case 4: Password field inside a nested list of objects is stripped."""
    data = {
        "claim_id": [
            {"password": "plain_password_123", "public_reference": "CLAIM-01"},
            {"public_reference": "CLAIM-02"},
        ]
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    items = sanitized["claim_id"]
    assert len(items) == 2
    assert "password" not in items[0]
    assert items[0]["public_reference"] == "CLAIM-01"
    assert items[1]["public_reference"] == "CLAIM-02"


def test_metadata_sanitization_5_uppercase_keys():
    """Case 5: Uppercase and mixed case keys are normalized and checked."""
    data = {
        "TOKEN": "secret_uppercase_token",
        "PASSWORD_HASH": "argon2_hash_val",
        "POST_ID": "post_uuid_here",
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    assert "token" not in sanitized
    assert "password_hash" not in sanitized
    assert sanitized["post_id"] == "post_uuid_here"


def test_metadata_sanitization_6_variant_key_names():
    """Case 6: Different naming variations (access_token, api_key, private_content, id_card) are stripped."""
    data = {
        "access_token": "token_val",
        "refresh_token": "refresh_val",
        "api_key": "key_val",
        "private_content": "private_note",
        "id_card": "123456789",
        "post_id": "safe_post_id",
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    assert "access_token" not in sanitized
    assert "refresh_token" not in sanitized
    assert "api_key" not in sanitized
    assert "private_content" not in sanitized
    assert "id_card" not in sanitized
    assert sanitized["post_id"] == "safe_post_id"


def test_metadata_sanitization_7_unapproved_fields_rejected():
    """Case 7: Fields not present in allowlist are rejected even if not containing explicit forbidden words."""
    data = {
        "unknown_custom_field": "some_value",
        "user_credit_score": "750",
        "claim_id": "valid_claim",
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    assert "unknown_custom_field" not in sanitized
    assert "user_credit_score" not in sanitized
    assert sanitized["claim_id"] == "valid_claim"


def test_metadata_sanitization_8_deeply_nested_levels():
    """Case 8: Deeply nested hierarchy (3+ levels) is inspected recursively."""
    data = {
        "post_id": {
            "level1": {
                "level2": {
                    "level3": {
                        "secret": "deep_secret_value",
                        "public_reference": "safe_deep_value",
                    }
                }
            }
        }
    }
    sanitized = NotificationService.sanitize_metadata(data)
    assert sanitized is not None
    level3 = sanitized["post_id"]["level1"]["level2"]["level3"]
    assert "secret" not in level3
    assert level3["public_reference"] == "safe_deep_value"


# ============================================================================
# Service Ownership & Validation Unit Tests
# ============================================================================

@pytest.mark.asyncio
async def test_unit_service_ownership_enforcement(db_session, test_user_a, test_user_b):
    """Calling mark_as_read on another user's notification raises NotFoundError (anti-enumeration 404)."""
    service = NotificationService()

    notif = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            event_id=uuid.uuid4(),
            recipient_id=test_user_a.id,
            event_type="SYSTEM",
            title="Notice for A",
            message="Content for A",
        ),
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.mark_as_read(db_session, notif.id, current_user_id=test_user_b.id)
    assert "không tồn tại hoặc không thuộc quyền sở hữu" in str(exc_info.value)

    # Marking non-existent ID raises NotFoundError
    with pytest.raises(NotFoundError):
        await service.mark_as_read(db_session, uuid.uuid4(), current_user_id=test_user_a.id)


@pytest.mark.asyncio
async def test_unit_service_inactive_recipient_rejected(db_session, test_inactive_user):
    """Creating a notification for an inactive recipient raises ValidationError."""
    service = NotificationService()
    with pytest.raises(ValidationError) as exc_info:
        await service.create_notification(
            db_session,
            NotificationCreateInternal(
                event_id=uuid.uuid4(),
                recipient_id=test_inactive_user.id,
                event_type="SYSTEM",
                title="Notice for Inactive",
                message="Cannot send to inactive",
            ),
        )
    assert "không ở trạng thái ACTIVE" in str(exc_info.value)
