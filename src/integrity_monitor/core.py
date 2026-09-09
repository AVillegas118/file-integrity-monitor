"""Creación y comparación de líneas base de integridad."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Mapping

from .models import ChangeReport, FileRecord


SCHEMA_VERSION = 1
CHUNK_SIZE = 64 * 1024


class IntegrityError(Exception):
    """Error esperado que puede mostrarse de forma sencilla en la CLI."""


def sha256_file(path: Path) -> str:
    """Calcula SHA-256 leyendo por bloques para no cargar todo el archivo."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        raise IntegrityError(f"no se pudo leer {path}: {exc}") from exc
    return digest.hexdigest()


def scan_directory(root: Path, excluded: set[Path] | None = None) -> dict[str, FileRecord]:
    """Recorre archivos normales y omite los enlaces simbólicos encontrados."""

    try:
        if root.is_symlink():
            raise IntegrityError("el directorio observado no puede ser un enlace simbólico")
        root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise IntegrityError(f"el directorio no existe o no es accesible: {root}") from exc
    if not root.is_dir():
        raise IntegrityError(f"la ruta no es un directorio: {root}")

    try:
        excluded_resolved = {path.resolve(strict=False) for path in (excluded or set())}
    except (OSError, RuntimeError) as exc:
        raise IntegrityError(f"no se pudo comprobar una ruta excluida: {exc}") from exc
    records: dict[str, FileRecord] = {}

    def walk_error(error: OSError) -> None:
        # Sin onerror, os.walk puede omitir una carpeta sin avisar.
        raise IntegrityError(f"no se pudo recorrer {error.filename}: {error}") from error

    try:
        for current, directories, files in os.walk(root, onerror=walk_error, followlinks=False):
            directories[:] = sorted(
                name for name in directories if not (Path(current) / name).is_symlink()
            )
            for name in sorted(files):
                path = Path(current) / name
                metadata = path.lstat()
                if not stat.S_ISREG(metadata.st_mode):
                    continue
                if path.resolve(strict=False) in excluded_resolved:
                    continue
                relative = path.relative_to(root).as_posix()
                records[relative] = FileRecord(sha256=sha256_file(path), size=metadata.st_size)
    except (OSError, RuntimeError) as exc:
        raise IntegrityError(f"no se pudo recorrer {root}: {exc}") from exc

    return dict(sorted(records.items()))


def save_baseline(path: Path, records: Mapping[str, FileRecord]) -> None:
    """Publica un JSON completo sin reemplazar archivos existentes."""

    # No resolver primero: resolve() ocultaría un enlace simbólico de destino.
    path = path.absolute()
    if path.is_symlink():
        raise IntegrityError("la línea base no puede ser un enlace simbólico")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": "sha256",
        "files": {name: records[name].to_dict() for name in sorted(records)},
    }

    temporary_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
        # link() hace visible el JSON completo y falla si el destino ya existe.
        os.link(temporary_name, path)
    except FileExistsError as exc:
        raise IntegrityError("la línea base ya existe; elige otro nombre para conservarla") from exc
    except OSError as exc:
        raise IntegrityError(f"no se pudo guardar la línea base: {exc}") from exc
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass


def load_baseline(path: Path) -> dict[str, FileRecord]:
    """Lee y valida el formato mínimo de una línea base."""

    try:
        if path.is_symlink():
            raise IntegrityError("la línea base no puede ser un enlace simbólico")
        if not stat.S_ISREG(path.stat().st_mode):
            raise IntegrityError("la línea base debe ser un archivo normal")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IntegrityError(f"no existe la línea base: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"la línea base no es válida: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise IntegrityError("versión de línea base no compatible")
    if payload.get("algorithm") != "sha256" or not isinstance(payload.get("files"), dict):
        raise IntegrityError("formato de línea base no válido")

    records: dict[str, FileRecord] = {}
    try:
        for name, value in payload["files"].items():
            if not isinstance(name, str) or not isinstance(value, dict):
                raise TypeError
            digest = value["sha256"]
            size = value["size"]
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
            ):
                raise TypeError
            records[name] = FileRecord(sha256=digest, size=size)
    except (KeyError, TypeError) as exc:
        raise IntegrityError("la lista de archivos de la línea base no es válida") from exc
    return records


def compare(
    baseline: Mapping[str, FileRecord], current: Mapping[str, FileRecord]
) -> ChangeReport:
    """Clasifica diferencias entre la línea base y el estado actual."""

    baseline_names = set(baseline)
    current_names = set(current)
    return ChangeReport(
        added=tuple(sorted(current_names - baseline_names)),
        modified=tuple(
            sorted(
                name
                for name in baseline_names & current_names
                if baseline[name] != current[name]
            )
        ),
        deleted=tuple(sorted(baseline_names - current_names)),
    )
