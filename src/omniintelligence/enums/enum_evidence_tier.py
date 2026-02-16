"""Evidence tier enum for pattern measurement attribution.

This enum represents the evidence quality tier for learned patterns,
progressing from UNMEASURED (no data) through OBSERVED (anecdotal)
and MEASURED (quantitative) to VERIFIED (independently validated).

Ordering Support:
    This enum supports comparison operators (<, >, <=, >=) for monotonic
    tier enforcement. Tiers are ordered by evidence strength:
        UNMEASURED < OBSERVED < MEASURED < VERIFIED

    Example:
        >>> EnumEvidenceTier.OBSERVED > EnumEvidenceTier.UNMEASURED
        True
        >>> EnumEvidenceTier.MEASURED > EnumEvidenceTier.VERIFIED
        False

Origin:
    This enum was intended for omnibase_core (OMN-2134) but is defined
    locally in omniintelligence because omnibase_core has not yet
    published it. If omnibase_core adds EnumEvidenceTier in the future,
    this local definition should be replaced with a re-export.

Reference:
    - OMN-2133: L1 Attribution Bridge (evidence tier computation)
    - OMN-2134: [omnibase_core] Add EnumEvidenceTier enum with ordering
"""

from enum import Enum

# Numeric weights for ordering. Defined outside the class to keep the
# enum body clean and avoid polluting member namespace.
_EVIDENCE_TIER_WEIGHTS: dict[str, int] = {
    "unmeasured": 0,
    "observed": 10,
    "measured": 20,
    "verified": 30,
}


class EnumEvidenceTier(str, Enum):
    """Evidence quality tier for learned patterns.

    Tiers are ordered by evidence strength and support comparison
    operators for monotonic enforcement (tiers only increase).

    Attributes:
        UNMEASURED: No measurement data available (default state).
        OBSERVED: Anecdotal evidence from workflow execution.
        MEASURED: Quantitative data from a successful pipeline run.
        VERIFIED: Independently validated (future capability).
    """

    UNMEASURED = "unmeasured"
    OBSERVED = "observed"
    MEASURED = "measured"
    VERIFIED = "verified"

    @property
    def _weight(self) -> int:
        return _EVIDENCE_TIER_WEIGHTS[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, EnumEvidenceTier):
            return NotImplemented
        return self._weight < other._weight

    def __le__(self, other: object) -> bool:
        if not isinstance(other, EnumEvidenceTier):
            return NotImplemented
        return self._weight <= other._weight

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, EnumEvidenceTier):
            return NotImplemented
        return self._weight > other._weight

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, EnumEvidenceTier):
            return NotImplemented
        return self._weight >= other._weight


__all__ = ["EnumEvidenceTier"]
