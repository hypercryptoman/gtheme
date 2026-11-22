# gtheme

gtheme is a keyboard-driven theme picker for Ghostty on macOS. It previews colors in the current terminal using a sample prompt, diff, code, and ANSI palette. Browse a curated selection of themes bundled with Ghostty, filter by name, and save the one you want.

[Project site](https://hypercryptoman.github.io/gtheme/)

## Install

You’ll need macOS, Ghostty, Python 3.8 or newer, and Git for the clone step. The command uses Python’s standard library.

```sh
git clone https://github.com/hypercryptoman/gtheme.git
cd gtheme
mkdir -p ~/.local/bin
install -m 755 gtheme ~/.local/bin/gtheme
```

Open a Ghostty window and run `~/.local/bin/gtheme`. If `~/.local/bin` is on your `PATH`, run `gtheme`.

## Use

```sh
gtheme
```

| Key | Action |
| --- | --- |
| ↑ / ↓ or `k` / `j` | Move one theme and preview it |
| Page Up / Page Down | Jump up or down by ten themes |
| `/` | Start a case-insensitive name filter |
| Backspace | Remove a character while editing the filter |
| Enter while filtering | Finish typing and keep the filtered results |
| Esc while filtering | Clear the filter and return to all themes |
| Enter while browsing | Save the highlighted theme |
| `q` or Esc while browsing | Cancel and restore the previous colors |
| Ctrl+C | Cancel from either mode |

Saving updates the `theme` setting in `~/.config/ghostty/config` by default and asks the running Ghostty process to reload. If the palette doesn’t update after saving, use Ghostty’s Reload Configuration menu item. The picker writes a single theme value. If you use an automatic light/dark pair, saving replaces the pair in the selected config.

### Command-line options

| Option | Purpose |
| --- | --- |
| `-h`, `--help` | Show usage and exit |
| `--config PATH` | Edit a different Ghostty config file. Choose a file Ghostty actually loads for the reload to apply. |
| `--themes-dir PATH` | Read themes from a different directory. By default the picker uses `/Applications/Ghostty.app/Contents/Resources/ghostty/themes`. |

### Examples

- **Compare Catppuccin variants.** Run `gtheme`, press `/`, type `catppuccin`, and press Enter. Use ↑ and ↓ to compare results. Press Enter again to save the highlighted variant.
- **Try Dracula and keep your current theme.** Press `/`, type `dracula`, and press Enter to leave the filter. Press `q` to exit with your config untouched.
- **Use a Ghostty installation in your home folder.** Run `gtheme --themes-dir "$HOME/Applications/Ghostty.app/Contents/Resources/ghostty/themes"`.
- **Use an alternate Ghostty config.** Run `gtheme --config "$HOME/Library/Application Support/com.mitchellh.ghostty/config"` if that’s the file Ghostty reads.

Theme availability depends on the files in your installed Ghostty bundle.
