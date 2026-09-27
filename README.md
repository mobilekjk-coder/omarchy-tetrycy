# Tetrycy — Omarchy plugin

Desktop aggregator for [Tetrycy](https://www.youtube.com/@Tetrycy): the main YouTube channel, [Tetrycy Forte](https://www.youtube.com/@TetrycyForte), guest appearances on Betclic Polska, and the commentators' personal X accounts.

Plugin id: `kjk.tetrycy`

> **Polish only.** Every Tetrycy source this plugin surfaces is in Polish — videos, tweets, titles, and the overlay copy. There is no English UI or translation.

Unofficial. Not affiliated with Tetrycy.

- **service** — refreshes sources in the background
- **bar-widget** — a bar pill labelled TETRYCY (highlights when they are live)
- **overlay** — videos on the left, X on the right

## Install

Needs [Omarchy](https://omarchy.org/) with a running `omarchy-shell`, plus `python3` on `PATH` (already present on a normal Omarchy install).

```bash
omarchy plugin add https://github.com/mobilekjk-coder/omarchy-tetrycy.git --enable
```

That clones the plugin into `~/.config/omarchy/plugins/kjk.tetrycy/` and puts the widget on the center of the bar.

Left click opens the overlay under the bar (the bar stays visible). Click the pill again, **ZAMKNIJ**, click outside the card, or press Esc to close. Middle click refreshes. Right click sends a desktop notification for the latest video. **R** refreshes while the overlay is open.

Update later with:

```bash
omarchy plugin update kjk.tetrycy
```

## Remove

```bash
omarchy plugin remove kjk.tetrycy
```

That disables the widget and deletes the checkout. Cached data in `~/.local/state/omarchy/kjk.tetrycy/` is left behind; delete that directory if you want it gone too.

## Sources

No API keys. Cache files under `~/.local/state/omarchy/kjk.tetrycy/` are created only when that directory and its files are real directories and regular files. A symlink in that chain is refused, so a cache write cannot be redirected elsewhere.

| Source | How |
|---|---|
| [Tetrycy](https://www.youtube.com/@Tetrycy) | Public YouTube RSS |
| [Tetrycy Forte](https://www.youtube.com/@TetrycyForte) | Public YouTube RSS |
| [Betclic x Tetrycy](https://www.youtube.com/playlist?list=PLtVXfLwhcMZLRH3LrqET_EdHU6HCnHOwX) | Playlist RSS |
| Live | `youtube.com/@handle/live` |
| X · [Leszek](https://x.com/leszekmilewski), [Olki](https://x.com/JOlkiewicz) | Public profile pages; the X tab splits the screen into two columns |
| [tetrycy.com.pl](https://www.tetrycy.com.pl/) | Footer link |
| [Patronite](https://patronite.pl/tetrycy) | Patron count |

## Settings

Set these on the bar entry (Setup, or `omarchy bar set`):

| Key | Default | Meaning |
|---|---|---|
| `refreshMinutes` | `10` | How often to refetch. Live checks run more often |
| `showShorts` | `true` | Include YouTube Shorts |
| `notifyNew` | `true` | Notify when a new video appears |

```bash
omarchy bar set kjk.tetrycy refreshMinutes 15
omarchy bar set kjk.tetrycy showShorts false
```

## License

MIT. See [LICENSE](LICENSE).
