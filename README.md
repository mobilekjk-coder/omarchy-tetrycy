# Tetrycy — Omarchy plugin

Aggregator [Tetrycy](https://www.youtube.com/@Tetrycy) na pulpicie: YouTube, Tetrycy Forte, gościnne odcinki Betclic i wpisy z X.

Plugin id: `kjk.tetrycy`

- **service** — odświeża źródła w tle
- **bar-widget** — pigułka na pasku z napisem TETRYCY (podświetla się przy NA ŻYWO)
- **overlay** — filmy i X

Kind `panel` (OSD) tu nie pasuje — to toasty głośności, nie biurko.

Nieoficjalne. Niezwiązane z Tetrycami.

## Install

Needs [Omarchy](https://omarchy.org/) with a running `omarchy-shell`, plus `python3` on `PATH` (already present on a normal Omarchy install).

```bash
omarchy plugin add https://github.com/mobilekjk-coder/omarchy-tetrycy.git --enable
```

That clones the plugin into `~/.config/omarchy/plugins/kjk.tetrycy/` and puts the widget on the center of the bar.

Lewy klik otwiera overlay pod paskiem (pasek zostaje widoczny). Ponowny klik pigułki, **ZAMKNIJ**, klik poza kartą albo Esc zamyka. Środkowy odświeża. Prawy — powiadomienie o najnowszym filmie. **R** odświeża.

Update later with:

```bash
omarchy plugin update kjk.tetrycy
```

## Remove

```bash
omarchy plugin remove kjk.tetrycy
```

That disables the widget and deletes the checkout. Cached data in `~/.local/state/omarchy/kjk.tetrycy/` is left behind; delete that directory if you want it gone too.

## Źródła

Bez kluczy API.

| Źródło | Jak |
|---|---|
| [Tetrycy](https://www.youtube.com/@Tetrycy) | Publiczny RSS YouTube |
| [Tetrycy Forte](https://www.youtube.com/@TetrycyForte) | Publiczny RSS YouTube |
| [Betclic x Tetrycy](https://www.youtube.com/playlist?list=PLtVXfLwhcMZLRH3LrqET_EdHU6HCnHOwX) | RSS playlisty |
| Na żywo | `youtube.com/@handle/live` |
| X · [Leszek](https://x.com/leszekmilewski), [Olki](https://x.com/JOlkiewicz) | Publiczne strony profili; zakładka X dzieli ekran na dwie kolumny |
| [tetrycy.com.pl](https://www.tetrycy.com.pl/) | Link w stopce |
| [Patronite](https://patronite.pl/tetrycy) | Liczba patronów |

## Settings

| Key | Default | Meaning |
|---|---|---|
| `refreshMinutes` | `10` | Jak często ściągać. Na żywo częściej |
| `showShorts` | `true` | YouTube Shorts |
| `notifyNew` | `true` | Powiadomienie o nowym filmie |

```bash
omarchy bar set kjk.tetrycy refreshMinutes 15
omarchy bar set kjk.tetrycy showShorts false
```

Source: [github.com/mobilekjk-coder/omarchy-tetrycy](https://github.com/mobilekjk-coder/omarchy-tetrycy)

## License

MIT. See [LICENSE](LICENSE).
