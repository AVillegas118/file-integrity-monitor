import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrity_monitor.core import (
    IntegrityError,
    compare,
    load_baseline,
    save_baseline,
    scan_directory,
    sha256_file,
)


class IntegrityMonitorTests(unittest.TestCase):
    def test_sha256_known_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary, "hello.txt")
            path.write_bytes(b"hello\n")
            self.assertEqual(
                sha256_file(path),
                "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
            )

    def test_detects_added_modified_and_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Path(root, "modified.txt").write_text("antes", encoding="utf-8")
            Path(root, "deleted.txt").write_text("se elimina", encoding="utf-8")
            baseline = scan_directory(root)

            Path(root, "modified.txt").write_text("después", encoding="utf-8")
            Path(root, "deleted.txt").unlink()
            Path(root, "added.txt").write_text("nuevo", encoding="utf-8")
            report = compare(baseline, scan_directory(root))

            self.assertEqual(report.added, ("added.txt",))
            self.assertEqual(report.modified, ("modified.txt",))
            self.assertEqual(report.deleted, ("deleted.txt",))

    def test_ignores_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = Path(root, "target.txt")
            target.write_text("contenido", encoding="utf-8")
            Path(root, "link.txt").symlink_to(target)

            snapshot = scan_directory(root)

            self.assertEqual(tuple(snapshot), ("target.txt",))

    def test_excludes_baseline_inside_observed_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_path = Path(root, "baseline.json")
            Path(root, "document.txt").write_text("dato", encoding="utf-8")

            snapshot = scan_directory(root, excluded={baseline_path})
            save_baseline(baseline_path, snapshot)
            current = scan_directory(root, excluded={baseline_path})

            self.assertEqual(compare(load_baseline(baseline_path), current).has_changes, False)

    def test_baseline_json_is_sorted_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Path(root, "z.txt").write_text("z", encoding="utf-8")
            Path(root, "a.txt").write_text("a", encoding="utf-8")
            records = scan_directory(root)
            baseline_path = Path(root, "baseline.json")

            save_baseline(baseline_path, records)

            payload = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(list(payload["files"]), ["a.txt", "z.txt"])
            self.assertEqual(load_baseline(baseline_path), records)

    def test_rejects_invalid_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary, "baseline.json")
            path.write_text('{"schema_version": 99}', encoding="utf-8")
            with self.assertRaises(IntegrityError):
                load_baseline(path)

    def test_rejects_a_symbolic_link_as_scan_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary, "root")
            root.mkdir()
            link = Path(temporary, "link")
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(IntegrityError):
                scan_directory(link)

    def test_does_not_scan_linked_subdirectories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary, "root")
            root.mkdir()
            outside = Path(temporary, "outside")
            outside.mkdir()
            (outside / "private.txt").write_text("dato", encoding="utf-8")
            (root / "link").symlink_to(outside, target_is_directory=True)
            self.assertEqual(scan_directory(root), {})

    def test_scan_reports_directory_permission_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch("os.scandir", side_effect=PermissionError("acceso denegado")):
                with self.assertRaises(IntegrityError):
                    scan_directory(Path(temporary))

    def test_baseline_does_not_overwrite_an_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary, "document.txt")
            path.write_text("contenido original", encoding="utf-8")
            with self.assertRaises(IntegrityError):
                save_baseline(path, {})
            self.assertEqual(path.read_text(encoding="utf-8"), "contenido original")
            self.assertEqual(list(Path(temporary).iterdir()), [path])

    def test_baseline_does_not_follow_a_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary, "original.json")
            save_baseline(target, {})
            original = target.read_bytes()
            link = Path(temporary, "baseline.json")
            link.symlink_to(target)
            with self.assertRaises(IntegrityError):
                save_baseline(link, {})
            with self.assertRaises(IntegrityError):
                load_baseline(link)
            self.assertEqual(target.read_bytes(), original)
            self.assertTrue(link.is_symlink())

    def test_non_utf8_baseline_has_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary, "baseline.json")
            path.write_bytes(b"\xff\xfe")
            with self.assertRaises(IntegrityError):
                load_baseline(path)


if __name__ == "__main__":
    unittest.main()
