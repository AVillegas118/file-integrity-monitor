import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from integrity_monitor.cli import main


class CliTests(unittest.TestCase):
    def test_create_then_check_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary, "watched")
            root.mkdir()
            Path(root, "config.txt").write_text("seguro=true", encoding="utf-8")
            baseline = Path(temporary, "baseline.json")

            with redirect_stdout(StringIO()):
                self.assertEqual(
                    main(["create", str(root), "--baseline", str(baseline)]), 0
                )
                self.assertEqual(
                    main(["check", str(root), "--baseline", str(baseline)]), 0
                )

    def test_check_returns_two_when_a_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary, "watched")
            root.mkdir()
            file_path = Path(root, "config.txt")
            file_path.write_text("antes", encoding="utf-8")
            baseline = Path(temporary, "baseline.json")
            with redirect_stdout(StringIO()):
                main(["create", str(root), "--baseline", str(baseline)])
            file_path.write_text("después", encoding="utf-8")

            output = StringIO()
            with redirect_stdout(output):
                code = main(["check", str(root), "--baseline", str(baseline)])

            self.assertEqual(code, 2)
            self.assertIn("[MODIFICADO] config.txt", output.getvalue())

    def test_missing_baseline_is_a_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            error = StringIO()
            with redirect_stderr(error):
                code = main(
                    [
                        "check",
                        temporary,
                        "--baseline",
                        str(Path(temporary, "missing.json")),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("no existe la línea base", error.getvalue())

    def test_create_rejects_symlink_without_changing_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary, "watched")
            root.mkdir()
            original = Path(root, "notes.txt")
            original.write_text("conservar", encoding="utf-8")
            baseline = Path(temporary, "baseline.json")
            baseline.symlink_to(original)
            with redirect_stderr(StringIO()):
                code = main(["create", str(root), "--baseline", str(baseline)])
            self.assertEqual(code, 1)
            self.assertEqual(original.read_text(encoding="utf-8"), "conservar")

    def test_invalid_baseline_parent_has_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary, "file.txt")
            parent.write_text("archivo", encoding="utf-8")
            with redirect_stderr(StringIO()):
                code = main(["create", temporary, "--baseline", str(parent / "base.json")])
            self.assertEqual(code, 1)

    def test_baseline_symbolic_link_loop_has_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary, "loop.json")
            baseline.symlink_to(baseline)
            with redirect_stderr(StringIO()):
                code = main(["create", temporary, "--baseline", str(baseline)])
            self.assertEqual(code, 1)
            self.assertTrue(baseline.is_symlink())


if __name__ == "__main__":
    unittest.main()
