"""Modelos de datos del monitor de integridad."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class FileRecord:
    sha256: str
    size: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChangeReport:
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

    def to_dict(self) -> dict[str, object]:
        return {
            "changed": self.has_changes,
            "summary": {
                "added": len(self.added),
                "modified": len(self.modified),
                "deleted": len(self.deleted),
            },
            "files": {
                "added": list(self.added),
                "modified": list(self.modified),
                "deleted": list(self.deleted),
            },
        }

