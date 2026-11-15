"""Patience / frustration budget (SPEC §7)."""

from dataclasses import dataclass, field


@dataclass
class Patience:
    max: int
    value: int = field(init=False)

    def __post_init__(self) -> None:
        self.value = self.max

    def update(
        self, *, screen_changed: bool, error_seen: bool, feeling: str, progress: bool
    ) -> list[str]:
        """Apply one step's events; return the reasons for any change (for the trace)."""
        reasons = []
        if not screen_changed:
            reasons.append("layar sama (-1)")
        if error_seen:
            reasons.append("pesan error (-1)")
        if feeling in ("kesal", "takut"):
            reasons.append(f"merasa {feeling} (-1)")
        delta = -len(reasons)
        if progress:
            reasons.append("ada kemajuan (+1)")
            delta += 1
        self.value = max(0, min(self.max, self.value + delta))
        return reasons

    @property
    def exhausted(self) -> bool:
        return self.value <= 0
