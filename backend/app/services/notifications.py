"""Pluggable onboarding-result notifications.

MVP is in-app only: the client learns the new status by reading the status/me
endpoint, so the in-app notifier is a no-op. A real SMS channel can be plugged
in by setting a notifier that actually sends — until then we never claim an SMS
was delivered.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models import OnboardingStatus, User


class Notifier(ABC):
    @abstractmethod
    def onboarding_status_changed(
        self, user: User, status: str, *, reason: str | None = None
    ) -> None: ...


class InAppNotifier(Notifier):
    def onboarding_status_changed(
        self, user: User, status: str, *, reason: str | None = None
    ) -> None:
        # Status is surfaced through the API; nothing to push here.
        return None


class SmsNotifier(Notifier):
    """Placeholder for a real SMS gateway. Intentionally a no-op until wired."""

    def onboarding_status_changed(
        self, user: User, status: str, *, reason: str | None = None
    ) -> None:
        return None


_notifier: Notifier = InAppNotifier()


def get_notifier() -> Notifier:
    return _notifier


def set_notifier(notifier: Notifier) -> None:
    global _notifier
    _notifier = notifier


__all__ = [
    "Notifier",
    "InAppNotifier",
    "SmsNotifier",
    "get_notifier",
    "set_notifier",
    "OnboardingStatus",
]
