"""Compatibility helpers for the broker ACL.

The ``vyapaar`` native wheel is optional at runtime; when present its canonical
primitives are available, otherwise pure-Python ``decimal.Decimal`` fallbacks
keep the package fully offline-testable.
"""

from __future__ import annotations

from decimal import Decimal

try:  # pragma: no cover - exercised only when the native wheel is absent
    from vyapaar import Decimal as VyapaarDecimal

    VYAAPAAR_AVAILABLE = True
except ImportError:  # pragma: no cover
    VyapaarDecimal = Decimal
    VYAAPAAR_AVAILABLE = False

D = Decimal
