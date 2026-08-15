"""Unit and integration tests for Notification Providers and Service (Phase 14)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.services.notification_service import (
    EmailNotificationProvider,
    NotificationEvent,
    NotificationService,
    NotificationType,
    NullNotificationProvider,
    SlackNotificationProvider,
)


@pytest.mark.asyncio
async def test_null_notification_provider_always_configured_and_logs() -> None:
    """NullNotificationProvider accepts any notification event cleanly without crashing."""
    provider = NullNotificationProvider()
    assert provider.name == "null"
    assert provider.is_configured() is True

    event = NotificationEvent(
        event_type=NotificationType.PROCESSING_COMPLETED,
        contract_id=str(uuid.uuid4()),
        contract_title="Test Vendor Agreement.pdf",
        org_id=str(uuid.uuid4()),
        summary="Processing completed successfully",
    )

    success = await provider.send_notification(event)
    assert success is True


@pytest.mark.asyncio
async def test_email_and_slack_skip_when_unconfigured() -> None:
    """Email and Slack providers gracefully skip when settings are missing."""
    with patch("app.services.notification_service.get_settings") as mock_settings:
        mock_settings.return_value.SMTP_HOST = None
        mock_settings.return_value.SLACK_WEBHOOK_URL = None

        email_prov = EmailNotificationProvider()
        slack_prov = SlackNotificationProvider()

        assert email_prov.is_configured() is False
        assert slack_prov.is_configured() is False

        event = NotificationEvent(
            event_type=NotificationType.HIGH_RISK_FINDING_DETECTED,
            contract_id=str(uuid.uuid4()),
            contract_title="High Risk MSA.pdf",
            org_id=str(uuid.uuid4()),
            recipient_email="legal@example.com",
            summary="Critical uncapped liability finding detected",
        )

        assert await email_prov.send_notification(event) is False
        assert await slack_prov.send_notification(event) is False


@pytest.mark.asyncio
async def test_notification_service_isolates_provider_exceptions() -> None:
    """If one provider raises an unhandled exception, other providers still execute
    and the service does NOT raise an error.
    """
    failing_provider = AsyncMock()
    failing_provider.name = "faulty_slack"
    failing_provider.send_notification.side_effect = RuntimeError("Slack gateway 502 Bad Gateway")

    working_provider = AsyncMock()
    working_provider.name = "healthy_null"
    working_provider.send_notification.return_value = True

    svc = NotificationService(providers=[failing_provider, working_provider])

    event = NotificationEvent(
        event_type=NotificationType.PROCESSING_FAILED,
        contract_id=str(uuid.uuid4()),
        contract_title="Failed Contract.pdf",
        org_id=str(uuid.uuid4()),
        summary="Document parsing failed",
    )

    # Should not raise exception
    await svc.dispatch(event)

    failing_provider.send_notification.assert_called_once_with(event)
    working_provider.send_notification.assert_called_once_with(event)
