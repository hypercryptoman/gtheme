"""Run with python3 -m unittest discover -s tests -v."""

import fcntl
import os
import pty
import runpy
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "gtheme.py"
GT = runpy.run_path(str(SCRIPT))


class PickerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.xdg = self.home / "xdg"
        self.bundle = self.home / "Example App/Ghostty.app/Contents/Resources/ghostty/themes"
        self.bundle.mkdir(parents=True)
        (self.bundle / "Nord").write_text("background = #2e3440\npalette = 1=#bf616a\n")
        (self.bundle / "Café").write_text("background = 1e1e2e\n")
        (self.bundle / "Broken").write_bytes(b"\xff")
        (self.bundle / "Bad, name").write_text("background = #123456\n")
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.xdg),
                        GHOSTTY_RESOURCES_DIR=str(self.bundle.parent), TERM="xterm-256color")
        self.config = self.home / "override.ghostty"

    def start_picker(self, *args, rows=32, columns=96):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
        state = termios.tcgetattr(slave)
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), *args],
            stdin=slave, stdout=slave, stderr=slave, env=self.env, start_new_session=True,
        )

        def reap():
            if process.poll() is None:
                process.kill()
            process.wait()

        self.addCleanup(reap)

        def read_until(expected):
            deadline = time.monotonic() + 5
            data = bytearray()
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.05)[0]:
                    data.extend(os.read(master, 65536))
                    if expected in data:
                        return bytes(data)
                elif process.poll() is not None:
                    break
            self.fail(f"missing {expected!r} in {data[-1000:]!r}")

        def exited(code=0):
            self.assertEqual(process.wait(timeout=5), code)
            restored = termios.tcgetattr(slave)
            # The kernel may mark input for reprocessing when canonical mode is restored.
            pending = getattr(termios, "PENDIN", 0)
            state[3] &= ~pending
            restored[3] &= ~pending
            self.assertEqual(restored, state)

        return process, master, slave, read_until, exited

    def test_theme_collections_classify_background_and_keep_curated_order(self):
        (self.bundle / "Catppuccin Latte").write_text("background = #eff1f5\n")
        (self.bundle / "Palette Only").write_text("palette = 1=#123abc\n")
        themes = {path.name: path for path in self.bundle.iterdir()}
        names = GT["collection_names"]
        self.assertEqual(names(themes, "top"), ["Nord", "Catppuccin Latte"])
        self.assertEqual(names(themes, "light"), ["Catppuccin Latte"])
        self.assertEqual(set(names(themes, "dark")), {"Nord", "Café", "Bad, name"})
        self.assertEqual(len(GT["TOP_THEMES"]), 50)

    def test_tab_cycles_lists_and_preserves_search(self):
        (self.bundle / "Nord Light").write_text("background = #e5e9f0\n")
        _, fd, _, read, exited = self.start_picker("--config", str(self.config))
        read(b"[All]  1/5")
        os.write(fd, b"\t")
        read(b"[Top 50]  1/2")
        os.write(fd, b"/nord\r\t")
        read(b"[Dark]  1/1  filter: nord")
        os.write(fd, b"\t")
        read(b"[Light]  1/1  filter: nord")
        os.write(fd, b"\x1b[Z")
        read(b"[Dark]  1/1  filter: nord")
        os.write(fd, b"q")
        read(b"Cancelled")
        exited()
        self.assertFalse(self.config.exists())

    def test_light_flag_starts_in_light_list_and_saves(self):
        (self.bundle / "Nord Light").write_text("background = #e5e9f0\n")
        _, fd, _, read, exited = self.start_picker("--light", "--no-reload", "--config", str(self.config))
        read(b"[Light]  1/1")
        os.write(fd, b"\r")
        read(b"Saved Nord Light")
        exited()
        self.assertEqual(self.config.read_text(), "theme = Nord Light\n")

    def test_cancel_leaves_config_and_restores_terminal(self):
        self.config.write_text("theme = Nord\n")
        _, fd, _, read, exited = self.start_picker("--config", str(self.config))
        self.assertIn(b"themes (4)", read(b"themes (4)"))
        os.write(fd, b"/nothing\r\x1b[6~\r")
        read(b"No matching themes")
        os.write(fd, b"q")
        read(b"Cancelled")
        exited()
        self.assertEqual(self.config.read_text(), "theme = Nord\n")

    def test_arrows_and_escape_clear_filter_then_cancel(self):
        self.config.write_text("theme = Nord\n")
        _, fd, _, read, exited = self.start_picker("--config", str(self.config))
        read(b"themes (4)")
        os.write(fd, b"\x1bOB")
        read(b" > Bad, name")
        os.write(fd, b"/caf")
        read(b"filter: caf_")
        os.write(fd, b"\x1b")
        read(b"themes (4)")
        os.write(fd, b"\x03")
        read(b"Cancelled")
        exited()
        self.assertEqual(self.config.read_text(), "theme = Nord\n")

    def test_home_and_end_jump_to_list_edges(self):
        self.config.write_text("theme = Nord\n")
        _, fd, _, read, exited = self.start_picker("--config", str(self.config))
        read(b"themes (4)")
        os.write(fd, b"\x1b[F")
        read(b"4/4")
        os.write(fd, b"\x1b[H")
        read(b"1/4")
        os.write(fd, b"\x1bOF")
        read(b"4/4")
        os.write(fd, b"q")
        read(b"Cancelled")
        exited()

    def test_save_reports_manual_reload_when_outside_ghostty(self):
        _, fd, _, read, exited = self.start_picker("--config", str(self.config))
        read(b"themes (4)")
        os.write(fd, b"\r")
        read(b"Reload Ghostty with Cmd+Shift+,")
        exited()
        self.assertEqual(self.config.read_text(), "theme = Nord\n")

    def test_utf8_filter_saves_explicit_directory_as_path(self):
        _, fd, _, read, exited = self.start_picker(
            "--themes-dir", str(self.bundle), "--config", str(self.config), "--no-reload",
        )
        read(b"themes (4)")
        os.write(fd, "/CAFÉ\r\r".encode())
        read("Saved Café".encode())
        exited()
        self.assertEqual(self.config.read_text(), f"theme = {self.bundle / 'Café'}\n")

    def test_resize_and_sigterm_restore_terminal(self):
        process, _, slave, read, exited = self.start_picker(rows=3, columns=28)
        read(b"gtheme")
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 96, 0, 0))
        read(b"themes (4)")
        process.send_signal(signal.SIGTERM)
        read(b"Cancelled")
        exited()
        self.assertFalse(self.config.exists())

    def test_invalid_preview_cannot_be_saved(self):
        _, fd, _, read, exited = self.start_picker("--config", str(self.config))
        read(b"gtheme")
        os.write(fd, b"/broken\r\r")
        read(b"Cannot select this theme")
        os.write(fd, b"q")
        read(b"Cancelled")
        exited()
        self.assertFalse(self.config.exists())

    def test_default_config_and_user_theme_override(self):
        custom = self.xdg / "ghostty/themes"
        custom.mkdir(parents=True)
        (custom / "Nord").write_text("background = #123456\n")
        support = self.home / "Library/Application Support/com.mitchellh.ghostty"
        support.mkdir(parents=True)
        (support / "config").write_text("font-size = 13\n")
        modern = support / "config.ghostty"
        modern.write_text("theme = Nord\n")
        _, fd, _, read, exited = self.start_picker("--no-reload")
        self.assertIn(b"\x1b]11;#123456\x1b\\", read(b"themes (4)"))
        os.write(fd, "/café\r\r".encode())
        read("Saved Café".encode())
        exited()
        self.assertEqual(modern.read_text(), "theme = Café\n")
        self.assertEqual((support / "config").read_text(), "font-size = 13\n")

    def test_config_save_preserves_other_bytes_and_symlink(self):
        target = self.home / "original"
        target.write_bytes(b"# comment\r\ntheme = Old\r\nfont-size = 13\r\ntheme = Nord")
        target.chmod(0o640)
        self.config.symlink_to(target)
        GT["save_theme"](self.config, "Café")
        self.assertTrue(self.config.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(target.read_bytes(), "# comment\r\ntheme = Old\r\nfont-size = 13\r\ntheme = Café".encode())

    def test_config_precedence_and_legacy_fallback(self):
        with patch.dict(os.environ, self.env):
            choose = GT["choose_config"]
            self.assertEqual(choose((1, 1, 0)).name, "config")
            self.assertEqual(choose((1, 4, 0)).name, "config.ghostty")
            legacy = self.xdg / "ghostty/config"
            legacy.parent.mkdir(parents=True)
            legacy.touch()
            self.assertEqual(choose((1, 4, 0)), legacy)

    def test_terminal_output_uses_validated_colors(self):
        theme = self.bundle / "Mixed"
        theme.write_bytes(
            b"background = #aabbcc\nforeground = \x1b]0;example-title\n"
            b"palette = 256=#ffffff\npalette = 15=012345\npalette = wrong=#ffffff\n"
        )
        self.assertEqual(
            GT["terminal_colors"](theme), "\x1b]4;15;#012345\x1b\\\x1b]11;#aabbcc\x1b\\"
        )
        with self.assertRaisesRegex(ValueError, "rename or move"):
            GT["theme_value"](self.bundle / "Bad, name", False)
        self.assertEqual(GT["fold"]("Cafe\u0301"), GT["fold"]("CAFÉ"))

    def test_reload_requires_confirmed_current_owner(self):
        main = GT["main"]
        for ownership, expected_calls in (
            ([(234, (1, 1, 0))], 0),
            ([(234, (1, 4, 0)), (999, (1, 4, 0))], 0),
            ([(234, (1, 4, 0)), (234, (1, 4, 0))], 1),
        ):
            with self.subTest(ownership=ownership):
                replacements = {
                    "owning_ghostty": Mock(side_effect=ownership),
                    "pick": Mock(return_value="Nord"),
                    "print": Mock(),
                }
                args = [str(SCRIPT), "--config", str(self.config)]
                with patch.dict(main.__globals__, replacements), patch.dict(os.environ, self.env), patch.object(sys, "argv", args), patch.object(sys.stdin, "isatty", return_value=True), patch.object(sys.stdout, "isatty", return_value=True), patch.object(os, "kill") as send_signal:
                    self.assertEqual(main(), 0)
                    self.assertEqual(send_signal.call_count, expected_calls)
                    if expected_calls:
                        send_signal.assert_called_once_with(234, signal.SIGUSR2)

    def test_help_and_non_interactive_error(self):
        def run(*args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), *args], env=self.env,
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
            )
        self.assertIn("--no-reload", run("--help").stdout)
        result = run()
        self.assertEqual(result.returncode, 2)
        self.assertIn("interactive Ghostty terminal", result.stderr)


if __name__ == "__main__":
    unittest.main()
