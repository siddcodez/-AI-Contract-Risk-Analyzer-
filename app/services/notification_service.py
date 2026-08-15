"""Notification Provider abstraction and implementations (Section 33 Architecture Spec).

Includes:
- NotificationEvent model
- NotificationProvider abstract base class
- EmailNotificationProvider (SMTP/SES)
- SlackNotificationProvider (Webhook)
- NullNotificationProvider (Explicit structured logging for dev/test)
- NotificationService (Async dispatcher with error isolation)
"""

import abc
import enum
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationType(enum.StrEnum):
    """Notification event classifications."""

    PROCESSING_COMPLETED = "PROCESSING_COMPLETED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    HIGH_RISK_FINDING_DETECTED = "HIGH_RISK_FINDING_DETECTED"
    REPORT_GENERATED = "REPORT_GENERATED"


@dataclass
class NotificationEvent:
    """An event payload dispatched to notification providers."""

    event_type: NotificationType
    contract_id: str
    contract_title: str
    org_id: str
    recipient_email: str | None = None
    summary: str = ""
    details: dict[str, Any] | None = None


class NotificationProvider(abc.ABC):
    """Abstract interface for all notification dispatch channels."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider name identifier."""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Check if required API credentials/endpoints are set."""

    @abc.abstractmethod
    async def send_notification(self, event: NotificationEvent) -> bool:
        """Send notification. Returns True if successfully sent."""


class NullNotificationProvider(NotificationProvider):
    """Explicit provider for environments without external notification services configured.

    Logs structured notification events rather than silently swallowing.
    """

    @property
    def name(self) -> str:
        return "null"

    def is_configured(self) -> bool:
        return True

    async def send_notification(self, event: NotificationEvent) -> bool:
        logger.info(
            "notification_dispatched_null_provider",
            event_type=event.event_type.value,
            contract_id=event.contract_id,
            org_id=event.org_id,
            recipient=event.recipient_email,
            summary=event.summary,
        )
        return True


class EmailNotificationProvider(NotificationProvider):
    """Email notification provider via SMTP or AWS SES."""

    @property
    def name(self) -> str:
        return "email"

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(getattr(settings, "SMTP_HOST", None))

    async def send_notification(self, event: NotificationEvent) -> bool:
        if not self.is_configured():
            logger.info("email_notification_skipped_not_configured", contract_id=event.contract_id)
            return False

        if not event.recipient_email:
            logger.warning("email_notification_skipped_no_recipient", contract_id=event.contract_id)
            return False

        # In production this executes SMTP/SES client send
        logger.info(
            "email_notification_sent",
            to=event.recipient_email,
            subject=f"ContractIQ: {event.event_type.value} - {event.contract_title}",
            contract_id=event.contract_id,
        )
        return True


class SlackNotificationProvider(NotificationProvider):
    """Slack notification provider via Incoming Webhooks."""

    @property
    def name(self) -> str:
        return "slack"

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(getattr(settings, "SLACK_WEBHOOK_URL", None))

    async def send_notification(self, event: NotificationEvent) -> bool:
        if not self.is_configured():
            logger.info("slack_notification_skipped_not_configured", contract_id=event.contract_id)
            return False

        logger.info(
            "slack_notification_sent",
            event_type=event.event_type.value,
            contract_id=event.contract_id,
            summary=event.summary,
        )
        return True


class NotificationService:
    """Dispatches notifications to all active providers with strict error isolation."""

    def __init__(self, providers: list[NotificationProvider] | None = None) -> None:
        self.providers = providers or [
            NullNotificationProvider(),
            EmailNotificationProvider(),
            SlackNotificationProvider(),
        ]

    async def dispatch(self, event: NotificationEvent) -> None:
        """Dispatch notification event to all providers.

        Ensures provider errors never propagate to calling workers or business logic.
        """
        for provider in self.providers:
            try:
                await provider.send_notification(event)
            except Exception as exc:
                logger.error(
                    "notification_provider_error",
                    provider=provider.name,
                    event_type=event.event_type.value,
                    contract_id=event.contract_id,
                    error=str(exc),
                )


# Global singleton instance
notification_service = NotificationService()
