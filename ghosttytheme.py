#!/usr/bin/env python3
"""Preview and save Ghostty themes from an interactive macOS terminal."""

import argparse
import contextlib
import fcntl
import os
import plistlib
import re
import select
import signal
import stat
import subprocess
import sys
import tempfile
import termios
import tty
import unicodedata
from pathlib import Path

APPLICATIONS = Path("/Applications/Ghostty.app")
THEME_SETTING = re.compile(r"^[ \t]*theme[ \t]*=[ \t]*([^\r\n]*)", re.MULTILINE)
COLORS = {"foreground": 10, "background": 11, "cursor-color": 12,
          "selection-background": 17, "selection-foreground": 19}
ANSI = re.compile(r"\033\[[0-9;]*m|.", re.DOTALL)
CSI = "\033["
OSC_END = "\033\\"
COLLECTIONS = {"all": "All", "top": "Top 50", "dark": "Dark", "light": "Light"}
# Match the published gallery order. Each name is a Ghostty theme filename.
TOP_THEMES = (
    'Catppuccin Mocha', 'TokyoNight Storm', 'Dracula', 'Nord', 'Gruvbox Dark', 'Rose Pine',
    'Kanagawa Wave', 'Everforest Dark Hard', 'Nightfox', 'GitHub Dark Default', 'Ayu Mirage',
    'One Half Dark', 'Catppuccin Macchiato', 'TokyoNight Night', 'Poimandres',
    'Solarized Dark Higher Contrast', 'Carbonfox', 'Material Ocean', 'Night Owl',
    'Flexoki Dark', 'Melange Dark', 'Monokai Pro', 'Selenized Dark', 'Cyberpunk', 'Horizon',
    'Rose Pine Moon', 'Iceberg Dark', 'Moonfly', 'Zenburn', 'Vercel', 'Catppuccin Latte',
    'Rose Pine Dawn', 'Gruvbox Light', 'GitHub Light Default', 'TokyoNight Day',
    'Kanagawa Lotus', 'Ayu Light', 'Nord Light', 'Dayfox', 'Everforest Light Med',
    'One Half Light', 'Atom One Light', 'Flexoki Light', 'Light Owl', 'Selenized Light',
    'Iceberg Light', 'iTerm2 Solarized Light', 'Melange Light', 'Alabaster', 'Tomorrow',
)
PREFERRED_THEMES = [
    'Catppuccin Mocha', 'Catppuccin Macchiato', 'Catppuccin Frappe', 'Catppuccin Latte',
    'TokyoNight', 'TokyoNight Storm', 'TokyoNight Night', 'Dracula', 'Gruvbox Dark',
    'Gruvbox Dark Hard', 'Nord', 'Rose Pine', 'Rose Pine Moon', 'Rose Pine Dawn',
    'Kanagawa Wave', 'Kanagawa Dragon', 'Everforest Dark Hard', 'Everforest Light Med',
    'Solarized Dark Higher Contrast', 'One Half Dark', 'Atom One Dark', 'Nightfox', 'Carbonfox',
    'Github Dark', 'Monokai Pro', 'Ayu Mirage', 'Zenburn', 'Synthwave', 'Poimandres',
    'Melange Dark', 'Github Light Default', 'Github Dark Default', 'GitHub Dark Dimmed',
    'Ayu Light', 'Material Darker', 'Material Ocean', 'Dawnfox', 'Dayfox', 'Duskfox', 'Nordfox',
    'Terafox', 'Night Owl', 'Light Owl', 'Cobalt2', 'Horizon', 'Sonokai', 'Moonfly',
    'Iceberg Dark', 'Iceberg Light', 'Tomorrow Night', 'Tomorrow Night Bright',
    'Tomorrow Night Burns', 'Tomorrow Night Eighties', 'Tomorrow', 'Snazzy',
    'Monokai Remastered', 'Monokai Soda', 'Monokai Vivid', 'Selenized Dark', 'Selenized Light',
    'Selenized Black', 'Gruvbox Light', 'Gruvbox Light Hard', 'Gruvbox Material',
    'Gruvbox Material Dark', 'Gruvbox Material Light', 'Kanagawa Lotus', 'TokyoNight Day',
    'Nord Light', 'Nord Wave', 'Challenger Deep', 'Cyberpunk', 'Dark Pastel', 'Darkside',
    'Doom One', 'Doom Peacock', 'Espresso', 'Fahrenheit', 'Flat', 'Flatland', 'Framer',
    'Fish Tank', 'Galaxy', 'Hardcore', 'Harper', 'Hax0r Blue', 'Hurtado', 'Hybrid',
    'Jackie Brown', 'Kibble', 'Laser', 'Liquid Carbon', 'Lovelace', 'Man Page', 'Mariana',
    'Mathias', 'Medallion', 'Mirage', 'Molokai', 'Monokai Pro Machine', 'Monokai Pro Octagon',
    'Monokai Pro Ristretto', 'Monokai Pro Spectrum', 'Neon', 'Neopolitan', 'Nvim Dark',
    'Nvim Light', 'Obsidian', 'Ocean', 'Oceanic Next', 'One Half Light', 'Atom One Light',
    'Onenord', 'Paraiso Dark', 'Pencil Dark', 'Pencil Light', 'Pro', 'Red Alert', 'Red Planet',
    'Rouge 2', 'Royal', 'Seafoam Pastel', 'Seoulbones Dark', 'Shades Of Purple', 'Slate',
    'Smyck', 'Spacedust', 'Spiderman', 'Square', 'Sundried', '0x96f', 'Abernathy', 'Agave Dusk',
    'Apple System Colors', 'Aubade', 'base16-icy', 'Black Metal (Burzum)', 'Blood Moon',
    'branch', 'Builtin Tango Light', 'Canyon Walnut', 'Cholla', 'CLRS', 'Copper Canyon',
    'Cutie Pro', 'datum (dark)', 'Desert Morning', 'Django Smooth', 'Earthsong', 'Embark',
    'Everforest Dark Med', 'Farmhouse Light', 'Forged in Steel', 'GitHub Dark', 'Glacier',
    'Graveyard Shift', 'Harvest Moon', 'High Desert Snow', 'Hopscotch.256', 'IC Orange PPL',
    'Isocon Light', 'iTerm2 Tango Light', 'Kanagawabones', 'Karma Light', 'Konsolas',
    'Liquid Carbon Transparent', 'Matcha Zen', 'Mesa Twilight', 'Modus Operandi Deuteranopia',
    'Monokai Pro Light', 'N0Tch2K', 'Night Lion V2', 'Noctis Hibernus', 'Novel', 'Onenord Light',
    'Painted Desert', 'Patina Light', 'Pierre Light', 'Possessed Toaster', 'Pumpkin Patch',
    'Raycast Dark', 'Rhoads Concord', 'Safety Glass', 'Sea Shells', 'SeedFlip Inkwell',
    'Sequoia Monochrome Light', 'Shokunin', 'SLOMP', 'Spacegray Bright', 'Stardust Voltage',
    'Sunset Drive', 'Tango Adapted', 'Thermal Receipt', 'Trapped in Amber', 'Undead', 'Vercel',
    'Warm Neon', 'Wryan', 'X Paris', 'Zacess Cream',
]


def xdg_config():
    configured = os.environ.get("XDG_CONFIG_HOME")
    root = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".config"
    return root / "ghostty"


def choose_config(version):
    app_support = Path.home() / "Library/Application Support/com.mitchellh.ghostty"
    locations = [
        app_support / "config.ghostty", app_support / "config",
        xdg_config() / "config.ghostty", xdg_config() / "config",
    ]
    return next(
        (path for path in locations if path.exists() or path.is_symlink()),
        app_support / ("config" if version and version < (1, 2, 3) else "config.ghostty"),
    )


def find_bundled_themes():
    candidates = []
    if os.environ.get("GHOSTTY_RESOURCES_DIR"):
        resources = Path(os.environ["GHOSTTY_RESOURCES_DIR"])
        candidates.extend([resources / "themes", resources / "ghostty/themes"])
    if os.environ.get("GHOSTTY_BIN_DIR"):
        candidates.append(Path(os.environ["GHOSTTY_BIN_DIR"]).parent / "Resources/ghostty/themes")
    for app in (APPLICATIONS, Path.home() / "Applications/Ghostty.app"):
        candidates.append(app / "Contents/Resources/ghostty/themes")
    return next((path for path in candidates if path.is_dir()), candidates[-2])


def fold(text):
    return unicodedata.normalize("NFC", text).casefold()


def theme_paths(bundled, explicit):
    themes = {}
    dirs = [bundled] if explicit else [bundled, xdg_config() / "themes"]
    for directory in dirs:
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and not path.name.startswith(".") and path.name.isprintable():
                    themes[path.name] = path
    if not explicit:
        custom = dirs[-1]
        # Look up the same spelling Ghostty will use on this filesystem.
        for name in themes:
            override = custom / name
            if override.is_file():
                themes[name] = override
    order = {}
    for index, name in enumerate(PREFERRED_THEMES):
        order.setdefault(fold(name), index)

    def sort_key(item):
        name = item[0]
        folded = fold(name)
        return order.get(folded, len(PREFERRED_THEMES)), folded, name

    return dict(sorted(themes.items(), key=sort_key))


def read_theme_colors(theme):
    palette = {}
    colors = {}
    with theme.open(encoding="utf-8-sig") as file:
        for line in file:
            if line.lstrip().startswith("#"):
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key == "palette":
                index, _, value = value.partition("=")
                index = index.strip()
                if not (1 <= len(index) <= 9 and index.isascii() and index.isdecimal()):
                    continue
                # Ghostty accepts up to 256 palette entries.
                index = int(index)
                if 0 <= index <= 255 and re.fullmatch(r"#?[0-9a-fA-F]{6}", value.strip()):
                    palette[index] = "#" + value.strip().lstrip("#")
            elif key in COLORS and re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
                colors[COLORS[key]] = "#" + value.lstrip("#")
    return palette, colors


def collection_names(themes, collection):
    if collection == "all":
        return list(themes)
    if collection == "top":
        return [name for name in TOP_THEMES if name in themes]

    names = []
    for name, path in themes.items():
        try:
            _, colors = read_theme_colors(path)
        except (OSError, UnicodeError):
            continue
        background = colors.get(COLORS["background"])
        if background:
            red, green, blue = bytes.fromhex(background[1:])
            # Use the same brightness cutoff as Ghostty's theme list.
            is_dark = (0.2126 * red + 0.7152 * green + 0.0722 * blue) < 127.5
            if is_dark == (collection == "dark"):
                names.append(name)
    return names


def terminal_colors(theme):
    palette, colors = read_theme_colors(theme)
    if not (palette or colors):
        raise ValueError("no supported color settings")
    return "".join(
        f"\033]4;{index};{value}{OSC_END}" for index, value in palette.items()
    ) + "".join(f"\033]{code};{value}{OSC_END}" for code, value in colors.items())


def reset_colors():
    return "".join(f"\033]{code}{OSC_END}" for code in (104, 110, 111, 112, 117, 119))


def config_bytes(path):
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return b"", None
    if not stat.S_ISREG(metadata.st_mode):
        raise OSError("config must be a regular file")
    return path.read_bytes(), metadata


def theme_value(path, explicit):
    value = str(path.absolute()) if explicit else path.name
    if not value.isprintable():
        raise ValueError("theme path contains control characters")
    if value != value.strip() or any(char in value for char in ',:="'):
        raise ValueError("Ghostty cannot use this filename as a single theme; rename or move the theme")
    return value


def save_theme(path, value):
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Lock the directory so concurrent picker instances read the latest config
    # before replacing it, including when invoked through a config symlink.
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        original, metadata = config_bytes(path)
        if metadata and not os.access(path, os.W_OK):
            raise PermissionError("config is read-only")
        encoding = "utf-8-sig" if original.startswith(b"\xef\xbb\xbf") else "utf-8"
        config = original.decode(encoding)
        setting = "theme = " + value
        matches = list(THEME_SETTING.finditer(config))
        if matches:
            # Ghostty uses the last setting; preserve earlier lines and their formatting.
            last = matches[-1]
            config = config[:last.start()] + setting + config[last.end():]
        else:
            newline = "\r\n" if "\r\n" in config else "\n"
            config += (newline if config and not config.endswith("\n") else "") + setting + newline

        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(config.encode(encoding))
                if metadata:
                    os.fchmod(output.fileno(), stat.S_IMODE(metadata.st_mode))
            if config_bytes(path)[0] != original:
                raise OSError("config changed during save; run gtheme and try again")
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    finally:
        os.close(directory)


def ghostty_version(executable):
    try:
        with (executable.parent.parent / "Info.plist").open("rb") as file:
            value = plistlib.load(file).get("CFBundleShortVersionString", "")
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
        return tuple(map(int, match.groups())) if match else None
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return None


def owning_ghostty():
    """Find the app that owns this terminal without signaling other instances."""
    try:
        # A nested or detached PTY is not the terminal owned by an app ancestor.
        if os.tcgetpgrp(sys.stdin.fileno()) != os.getpgrp():
            return None, None
    except OSError:
        return None, None
    pid = os.getppid()
    while pid > 1:
        try:
            parent, command = subprocess.check_output(
                ["/bin/ps", "-p", str(pid), "-o", "ppid=", "-o", "comm="],
                text=True, stderr=subprocess.DEVNULL,
            ).strip().split(maxsplit=1)
        except (OSError, ValueError, subprocess.SubprocessError):
            break
        executable = Path(command)
        if executable.is_absolute() and executable.parts[-3:] == ("Contents", "MacOS", "ghostty"):
            return pid, ghostty_version(executable)
        pid = int(parent)
    return None, None


def read_key(fd):
    key = os.read(fd, 1)
    if key == b"\x1b":
        if not select.select([fd], [], [], 0.05)[0]:
            return "\x1b"
        key += os.read(fd, 1)
        if key in (b"\x1b[", b"\x1bO"):
            while len(key) < 32 and select.select([fd], [], [], 0.05)[0]:
                part = os.read(fd, 1)
                if not part:
                    break
                key += part
                if 0x40 <= part[0] <= 0x7e:
                    break
        return key.decode("ascii", errors="ignore")
    if key and 0xC2 <= key[0] <= 0xF4:
        length = 2 if key[0] < 0xE0 else 3 if key[0] < 0xF0 else 4
        for _ in range(length - 1):
            if not select.select([fd], [], [], 0.05)[0]:
                break
            key += os.read(fd, 1)
    return key.decode("utf-8", errors="replace")


def clip(text, columns):
    result = []
    width = 0
    for token in ANSI.findall(text):
        if token.startswith(CSI):
            result.append(token)
            continue
        if not unicodedata.combining(token):
            width += 2 if unicodedata.east_asian_width(token) in ("F", "W") else 1
        if width > columns:
            break
        result.append(token)
    return "".join(result) + CSI + "0m"


def sample_lines():
    def c(code, value):
        return f"{CSI}{code}m{value}{CSI}0m"

    R, G, Y, B, M, C, DIM = 31, 32, 33, 34, 35, 36, 90
    return [
        c(G,"➜")+" "+c(C,"~/demo")+" "+c(M,"git:(")+c(R,"demo")+c(M,")")+" "+c(Y,"✗")+" git status -sb",
        "## demo...origin/demo [ahead 2]",
        c(G," M")+" src/auth/session.ts    "+c(G," M")+" src/routes/login.ts",
        c(R,"??")+" tests/config.spec.ts    "+c(R,"??")+" notes.txt",
        "",
        c(G,"➜")+" "+c(C,"~/demo")+" git diff src/auth/session.ts",
        c(B,"@@ -12,7 +12,9 @@")+" export async function verify(token: string) {",
        c(R,"-  const user = jwt.decode(token)"),
        c(G,"+  const user = await jwt.verify(token, demoKey, { algorithms: ['HS256'] })"),
        c(G,"+  if (!user) throw new AuthError('invalid token')"),
        "   return db.users.find({ id: user.sub })",
        "",
        c(M,"import")+" "+c(Y,"os")+", "+c(Y,"json")+"  "+c(DIM,"# python"),
        c(M,"def")+" "+c(B,"load_config")+"("+c(Y,"path")+": "+c(C,"str")+") -> "+c(C,"dict")+":",
        "    "+c(M,"with")+" "+c(B,"open")+"(path) "+c(M,"as")+" f:  "+c(M,"return")+" json."+c(B,"load")+"(f)  "+c(DIM,"# 42, True, None"),
        "    "+c(M,"print")+"("+c(G,"f\"loaded {len(cfg)} keys\"")+", "+c(Y,"3.14")+", "+c(Y,"True")+")",
        "",
        c(G,"➜")+" "+c(C,"~/demo")+" npm test",
        c(G," ✓")+" login returns 200 for valid creds "+c(DIM,"(12ms)"),
        c(G," ✓")+" session expires after 30m "+c(DIM,"(4ms)"),
        c(R," ✗")+" rejects forged token  "+c(R,"AssertionError: expected 401, got 200"),
        c(Y," ⚠")+" "+c(Y,"warn")+" deprecated: Buffer() is unsafe, use Buffer.from()",
        c(R,"Tests:")+" "+c(R,"1 failed")+", "+c(G,"2 passed")+", 3 total",
        "",
        c(B,"drwxr-xr-x")+"  "+c(B,"src/")+"  "+c(B,"tests/")+"  "+c(G,"deploy.sh")+"  "+c(Y,"README.md")+"  "+c(C,"link → src/")+"  "+c(R,"backup.tar.gz"),
        "CPU "+c(G,"██████")+c(Y,"███")+c(R,"█")+c(DIM,"░░░░░")+" 54%   MEM "+c(B,"███████")+c(DIM,"░░░░░░░")+" 3.1G",
        "",
    ]


def draw(rows, cols, collection, view, selected, query, typing, issue):
    count = len(view)
    status = f"{selected + 1 if count else 0}/{count}"
    if query or typing:
        status += f"  filter: {query}" + ("_" if typing else "")
    controls = ("Enter done  Esc clear" if typing else "Tab lists  ↑↓ preview  / filter  Enter save  q cancel")
    heading = f"{CSI}1m gtheme{CSI}0m  [{COLLECTIONS[collection]}]  {status}  {controls}"
    current = view[selected] if view else "No matching themes"
    highlight = f"{CSI}7m > {current} {CSI}0m"
    lines = [heading]
    if rows < 8 or cols < 42:
        lines.append(highlight)
        if issue:
            lines.append(issue)
    else:
        def nearby(offset):
            return view[(selected + offset) % count] if view else ""

        if count:
            lines.append(f" ‹ {nearby(-1)}  {highlight}  {nearby(1)} ›")
        else:
            lines.append("No matching themes. Press Tab to switch lists.")
        lines.append("".join(f"{CSI}3{i}m██{CSI}9{i}m██{CSI}0m " for i in range(8)))
        if issue:
            lines.append(issue)
        reserved = min(10, count)
        lines.extend(sample_lines()[:max(0, rows - len(lines) - reserved - 1)])
        if count:
            lines.append(f"── themes ({count}) " + "─" * 46)
            room = max(0, rows - len(lines))
            start = max(0, min(selected - room // 2, count - room))
            for index in range(start, min(count, start + room)):
                lines.append(highlight if index == selected else "   " + view[index])
    screen = "\r\n".join(clip(line, max(1, cols - 1)) + CSI + "K" for line in lines[:rows])
    sys.stdout.write(CSI + "H" + CSI + "2J" + screen)
    sys.stdout.flush()


def interrupt(_signum, _frame):
    raise KeyboardInterrupt


def pick(themes, original, explicit=False, collection="all"):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    collections = tuple(COLLECTIONS)
    names = collection_names(themes, collection)
    cached = {collection: names}
    view = names
    selected = next(
        (i for i, name in enumerate(names) if original in (name, str(themes[name].absolute()))),
        0,
    )
    query = ""
    typing = False
    previewed = None
    issue = ""

    def filter_names():
        search = fold(query)
        return [name for name in names if search in fold(name)] if search else names

    handlers = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        tty.setraw(fd)
        sys.stdout.write(CSI + "?1049h" + CSI + "?25l")
        while True:
            current = view[selected] if view else None
            if current != previewed:
                sys.stdout.write(reset_colors())
                issue = ""
                if current:
                    try:
                        sys.stdout.write(terminal_colors(themes[current]))
                        theme_value(themes[current], explicit)
                    except (OSError, UnicodeError, ValueError) as error:
                        issue = f"Cannot select this theme: {error}"
                previewed = current

            size = os.get_terminal_size(fd)
            draw(size.lines or 24, size.columns or 80, collection, view, selected, query, typing, issue)
            while not select.select([fd], [], [], 0.15)[0]:
                if os.get_terminal_size(fd) != size:
                    break
            else:
                key = read_key(fd)
                if not key or key == "\x03":
                    return None
                if key in ("\t", "\x1b[Z"):
                    direction = 1 if key == "\t" else -1
                    collection = collections[(collections.index(collection) + direction) % len(collections)]
                    if collection not in cached:
                        cached[collection] = collection_names(themes, collection)
                    names = cached[collection]
                    view = filter_names()
                    selected = view.index(current) if current in view else 0
                elif typing:
                    if key in ("\r", "\n"):
                        typing = False
                        continue
                    if key == "\x1b":
                        query = ""
                        typing = False
                    elif key in ("\x7f", "\b"):
                        query = query[:-1]
                    elif key.isprintable() and len(query) < 256:
                        query += key
                    else:
                        continue
                    view = filter_names()
                    selected = 0
                elif key in ("\x1b[A", "\x1bOA", "k"):
                    selected = (selected - 1) % max(1, len(view))
                elif key in ("\x1b[B", "\x1bOB", "j"):
                    selected = (selected + 1) % max(1, len(view))
                elif key == "\x1b[5~":
                    selected = max(0, selected - 10)
                elif key == "\x1b[6~":
                    selected = min(max(0, len(view) - 1), selected + 10)
                elif key == "/":
                    query, view, selected, typing = "", names, 0, True
                elif key in ("\r", "\n") and current and not issue:
                    return current
                elif key in ("q", "\x1b"):
                    return None
    except KeyboardInterrupt:
        return None
    finally:
        with contextlib.suppress(OSError):
            termios.tcsetattr(fd, termios.TCSANOW, old)
        with contextlib.suppress(OSError):
            sys.stdout.write(CSI + "0m" + reset_colors() + CSI + "?25h" + CSI + "?1049l")
            sys.stdout.flush()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description="Preview and save Ghostty themes on macOS.")
    parser.add_argument("--config", type=Path, help="Ghostty config to edit")
    parser.add_argument("--themes-dir", type=Path, help="Read themes from this directory")
    parser.add_argument("--no-reload", action="store_true", help="Save without signaling Ghostty")
    lists = parser.add_mutually_exclusive_group()
    lists.add_argument("--top", dest="collection", action="store_const", const="top",
                       help="Start in the curated Top 50 list")
    lists.add_argument("--dark", dest="collection", action="store_const", const="dark",
                       help="Start with dark themes")
    lists.add_argument("--light", dest="collection", action="store_const", const="light",
                       help="Start with light themes")
    parser.set_defaults(collection="all")
    args = parser.parse_args()
    if sys.version_info < (3, 8):
        parser.error("Python 3.8 or newer is required")
    if not (sys.stdin.isatty() and sys.stdout.isatty()) or os.environ.get("TERM") == "dumb":
        parser.error("open gtheme in an interactive Ghostty terminal")

    pid, version = owning_ghostty()
    directory = args.themes_dir.expanduser() if args.themes_dir else find_bundled_themes()
    config = args.config.expanduser() if args.config else choose_config(version)
    try:
        themes = theme_paths(directory, args.themes_dir is not None)
        if not themes:
            parser.error(f"no themes found in {directory}; check Ghostty or pass --themes-dir")
        settings = THEME_SETTING.findall(config_bytes(config)[0].decode("utf-8-sig"))
        original = settings[-1].strip().strip('"') if settings else None
        chosen = pick(themes, original, args.themes_dir is not None, args.collection)
        if not chosen:
            print("Cancelled. Ghostty config was not changed.")
            return 0
        # Recheck the file in case the app or theme was updated during browsing.
        terminal_colors(themes[chosen])
        save_theme(config, theme_value(themes[chosen], args.themes_dir is not None))
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        parser.exit(1, f"gtheme: {error}\n")

    print(f"Saved {chosen} to {config}.")
    if not args.no_reload:
        if pid and version and version >= (1, 2, 3) and owning_ghostty() == (pid, version):
            try:
                os.kill(pid, signal.SIGUSR2)
                return 0
            except OSError:
                pass
        print("Reload Ghostty with Cmd+Shift+, to apply the theme.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
