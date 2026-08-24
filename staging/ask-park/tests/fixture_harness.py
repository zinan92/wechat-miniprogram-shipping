"""Hermetic record/replay primitives for staged Ask Park tests."""


class ExternalSideEffectError(AssertionError):
    """Raised when a fixture attempts network or external mutation."""


class RecordReplayAdapter:
    """Read deterministic fixture values without network or external writes."""

    def __init__(self, records):
        self._records = dict(records)
        self.events = []

    def read(self, key):
        if key not in self._records:
            raise KeyError(key)
        self.events.append({"kind": "read", "key": key})
        return self._records[key]


def assert_no_external_side_effects(events):
    forbidden = {"network", "mutation", "upload", "delete", "payment", "review"}
    violations = [event for event in events if event.get("kind") in forbidden]
    if violations:
        raise ExternalSideEffectError(f"external fixture side effect: {violations!r}")
