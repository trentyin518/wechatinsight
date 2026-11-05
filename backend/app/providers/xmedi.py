"""Xmedi (极媒) adapter.

Shares the Qovia request shape until Xmedi's real endpoints are validated in
Phase 0; only the ``provider`` label differs so stored provenance stays correct.
"""

from __future__ import annotations

from app.providers.qovia import QoviaProvider


class XmediProvider(QoviaProvider):
    name = "xmedi"
