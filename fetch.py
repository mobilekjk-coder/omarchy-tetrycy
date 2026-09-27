#!/usr/bin/env python3
"""Pull a Tetrycy bundle for the Omarchy widget.

YouTube RSS is the reliable source.
X posts come from the public profile pages.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

UA = "kjk.tetrycy-omarchy/0.1 (personal Omarchy widget)"
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

STATE_DIR = Path.home() / ".local" / "state" / "omarchy" / "kjk.tetrycy"
MEDIA_DIR = STATE_DIR / "media"

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_MEDIA_BYTES = 2 * 1024 * 1024
MAX_CACHE_BYTES = 40 * 1024 * 1024
MAX_CACHE_FILES = 400
MAX_STATE_FILE_BYTES = 8 * 1024 * 1024
MEDIA_NAME = re.compile(r"[0-9a-f]{20}\.jpg")

# Hosts we are willing to contact. Media URLs from third-party JSON/HTML are
# still checked against this list before download or before they reach QML.
ALLOWED_DOCUMENT_HOSTS = frozenset({
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "i.ytimg.com",
    "patronite.pl",
    "www.patronite.pl",
    "api.fxtwitter.com",
    "fxtwitter.com",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
    "nitter.poast.org",
    "xcancel.com",
    "rss.xcancel.com",
    "nitter.tiekoetter.com",
})
ALLOWED_MEDIA_HOSTS = frozenset({
    "i.ytimg.com",
    "ytimg.com",
    "img.youtube.com",
    "pbs.twimg.com",
    "abs.twimg.com",
    "ton.twimg.com",
})
ALLOWED_MEDIA_SUFFIXES = (".twimg.com", ".ytimg.com")

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"
RSS = ""

CHANNELS = {
    "tetrycy": {
        "id": "tetrycy",
        "label": "Tetrycy",
        "handle": "Tetrycy",
        "channel_id": "UCjLqNDkyLqzrHeR6PiTk9LQ",
        "url": "https://www.youtube.com/@Tetrycy",
        "kind": "youtube",
    },
    "forte": {
        "id": "forte",
        "label": "Tetrycy Forte",
        "handle": "TetrycyForte",
        "channel_id": "UCSFVJ8koxwI0tcPwg8brNUg",
        "url": "https://www.youtube.com/@TetrycyForte",
        "kind": "youtube",
    },
}

GUESTS = {
    "betclic": {
        "id": "betclic",
        "label": "Betclic x Tetrycy",
        "playlist_id": "PLtVXfLwhcMZLRH3LrqET_EdHU6HCnHOwX",
        "url": "https://www.youtube.com/playlist?list=PLtVXfLwhcMZLRH3LrqET_EdHU6HCnHOwX",
        "kind": "guest",
    },
}

X_ACCOUNTS = [
    {"id": "x-leszek", "label": "Leszek Milewski", "handle": "leszekmilewski"},
    {"id": "x-kuba", "label": "Jakub Olkiewicz", "handle": "JOlkiewicz"},
]

NITTER_RSS = [
    "https://nitter.poast.org/{handle}/rss",
    "https://xcancel.com/{handle}/rss",
    "https://nitter.tiekoetter.com/{handle}/rss",
]

LINKS = [
    {"id": "youtube", "title": "YouTube Tetrycy", "url": "https://www.youtube.com/@Tetrycy"},
    {"id": "forte", "title": "YouTube Tetrycy Forte", "url": "https://www.youtube.com/@TetrycyForte"},
    {"id": "site", "title": "tetrycy.com.pl", "url": "https://www.tetrycy.com.pl/"},
    {"id": "patronite", "title": "Patronite", "url": "https://patronite.pl/tetrycy"},
    {"id": "discord", "title": "Discord Uniwersum", "url": "https://discord.gg/uniwersumpolskiejpilki"},
    {"id": "x-leszek", "title": "X · Leszek", "url": "https://x.com/leszekmilewski"},
    {"id": "x-kuba", "title": "X · Olki", "url": "https://x.com/JOlkiewicz"},
]


def now_ms() -> int:
    return int(time.time() * 1000)


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except FileNotFoundError:
        return False


def _ensure_dir_nofollow(path: Path, anchor: Path) -> None:
    """Create path under anchor. Refuse if any component from anchor down is a symlink."""
    path = path.expanduser()
    anchor = anchor.expanduser()
    if not path.is_absolute() or not anchor.is_absolute():
        raise OSError("state path must be absolute")
    try:
        rel = path.relative_to(anchor)
    except ValueError as exc:
        raise OSError("state path escapes home") from exc
    current = anchor
    for part in rel.parts:
        if part in ("", ".", ".."):
            raise OSError("bad state path")
        current = current / part
        if _is_symlink(current):
            raise OSError("refusing symlinked state path")
        if not os.path.lexists(current):
            os.mkdir(current, 0o700)
            continue
        mode = os.lstat(current).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise OSError("state path is not a directory")


def _assert_regular_or_absent(path: Path) -> None:
    if not os.path.lexists(path):
        return
    mode = os.lstat(path).st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise OSError("refusing non-regular state file")


def ensure_state_tree() -> Path:
    root = STATE_DIR
    _ensure_dir_nofollow(root, Path.home())
    _ensure_dir_nofollow(MEDIA_DIR, Path.home())
    _assert_regular_or_absent(root / "cache.json")
    _assert_regular_or_absent(root / "seen.json")
    return root


def write_nofollow(path: Path, data: bytes) -> None:
    if _is_symlink(path.parent) or _is_symlink(path):
        raise OSError("refusing symlink")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("refusing non-regular state file")
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    finally:
        os.close(fd)


def write_state_file(kind: str, payload: bytes) -> None:
    if kind not in ("cache", "seen"):
        raise OSError("unknown state file")
    if len(payload) > MAX_STATE_FILE_BYTES:
        raise OSError("state file too large")
    root = ensure_state_tree()
    write_nofollow(root / (kind + ".json"), payload)


def _is_blocked_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _host_allowed(host: str, media: bool) -> bool:
    host = host.lower().rstrip(".")
    if not host or host == "localhost":
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    if host in ALLOWED_DOCUMENT_HOSTS:
        return True
    if media and (host in ALLOWED_MEDIA_HOSTS or any(host.endswith(suf) for suf in ALLOWED_MEDIA_SUFFIXES)):
        return True
    return False


def assert_fetch_url(url: str, media: bool = False) -> urllib.parse.ParseResult:
    raw = (url or "").strip()
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("blocked scheme")
    if parsed.username or parsed.password:
        raise ValueError("blocked userinfo")
    if parsed.port not in (None, 443):
        raise ValueError("blocked port")
    host = parsed.hostname or ""
    if not _host_allowed(host, media=media):
        raise ValueError("blocked host")
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("unresolved host") from exc
    if not infos:
        raise ValueError("unresolved host")
    for info in infos:
        if _is_blocked_ip(info[4][0]):
            raise ValueError("blocked address")
    return parsed


def _read_limited(resp, limit: int) -> bytes:
    length = resp.headers.get("Content-Length")
    if length and str(length).isdigit() and int(length) > limit:
        raise ValueError("response too large")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = resp.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError("response too large")
        chunks.append(chunk)
    return b"".join(chunks)


class GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, media: bool = False):
        super().__init__()
        self._media = media

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        assert_fetch_url(newurl, media=self._media)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_https(url: str, timeout: float, headers: dict, media: bool, limit: int):
    assert_fetch_url(url, media=media)
    req = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(GuardedRedirectHandler(media=media))
    return opener.open(req, timeout=timeout), limit


def http_get(url: str, timeout: float = 8, browser: bool = False, headers: dict | None = None) -> tuple[str, str]:
    hdrs = {
        "User-Agent": BROWSER_UA if browser else UA,
        "Accept": "*/*",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }
    if headers:
        hdrs.update(headers)
    resp, limit = _open_https(url, timeout, hdrs, media=False, limit=MAX_DOCUMENT_BYTES)
    with resp:
        body = _read_limited(resp, limit).decode("utf-8", "replace")
        return resp.geturl(), body


def _prune_media_cache() -> None:
    try:
        ensure_state_tree()
    except OSError:
        return
    files = []
    try:
        names = os.listdir(MEDIA_DIR)
    except OSError:
        return
    for name in names:
        if not MEDIA_NAME.fullmatch(name):
            continue
        path = MEDIA_DIR / name
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            continue
        files.append((st.st_mtime, st.st_size, path))
    files.sort()
    total = sum(size for _, size, _ in files)
    while files and (total > MAX_CACHE_BYTES or len(files) > MAX_CACHE_FILES):
        _, size, victim = files.pop(0)
        try:
            st = os.lstat(victim)
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                continue
            os.unlink(victim)
            total -= size
        except OSError:
            pass


def cache_media(url: str) -> str:
    href = (url or "").strip()
    if not href:
        return ""
    try:
        assert_fetch_url(href, media=True)
        ensure_state_tree()
    except (ValueError, OSError):
        return ""
    digest = hashlib.sha1(href.encode("utf-8", "replace")).hexdigest()[:20]
    path = MEDIA_DIR / (digest + ".jpg")
    try:
        st = os.lstat(path)
        if stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode) and 200 < st.st_size <= MAX_MEDIA_BYTES:
            return path.as_uri()
    except FileNotFoundError:
        pass
    except OSError:
        return ""
    try:
        hdrs = {"User-Agent": BROWSER_UA, "Accept": "image/*,*/*"}
        resp, limit = _open_https(href, 8, hdrs, media=True, limit=MAX_MEDIA_BYTES)
        with resp:
            blob = _read_limited(resp, limit)
        if len(blob) < 200:
            return ""
        write_nofollow(path, blob)
        _prune_media_cache()
        return path.as_uri()
    except Exception:
        return ""


def localize_photos(photos: list) -> list:
    out = []
    for photo in photos or []:
        if isinstance(photo, dict):
            row = dict(photo)
            row["url"] = cache_media(str(row.get("url") or ""))
            if row["url"]:
                out.append(row)
        elif photo:
            local = cache_media(str(photo))
            if local:
                out.append({"url": local, "width": 16, "height": 9})
    return out


def safe_get(url: str, timeout: float = 8, browser: bool = False, headers: dict | None = None) -> tuple[str | None, str | None, str | None]:
    try:
        final, body = http_get(url, timeout=timeout, browser=browser, headers=headers)
        return final, body, None
    except Exception as exc:
        return None, None, str(exc)


def parse_time(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return 0


def text_of(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return unescape(el.text).strip()


def child(el: ET.Element, *names: str) -> ET.Element | None:
    for name in names:
        found = el.find(name)
        if found is not None:
            return found
    return None


def parse_atom_entries(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall(f"{ATOM}entry") or root.findall("entry"):
        video_id = text_of(child(entry, f"{YT}videoId", "yt:videoId"))
        title = text_of(child(entry, f"{ATOM}title", "title"))
        published = text_of(child(entry, f"{ATOM}published", "published"))
        link = ""
        for ln in entry.findall(f"{ATOM}link") + entry.findall("link"):
            href = ln.attrib.get("href") or ""
            if href:
                link = href
                if ln.attrib.get("rel", "alternate") in ("alternate", ""):
                    break
        author = text_of(child(child(entry, f"{ATOM}author", "author"), f"{ATOM}name", "name"))
        group = child(entry, f"{MEDIA}group", "media:group")
        thumb = ""
        views = 0
        description = ""
        if group is not None:
            thumb_el = child(group, f"{MEDIA}thumbnail", "media:thumbnail")
            if thumb_el is not None:
                thumb = thumb_el.attrib.get("url") or ""
            description = text_of(child(group, f"{MEDIA}description", "media:description"))
            stats = child(group, f"{MEDIA}community/{MEDIA}statistics", "media:community")
            community = child(group, f"{MEDIA}community")
            if community is not None:
                stats = child(community, f"{MEDIA}statistics")
                if stats is not None:
                    try:
                        views = int(stats.attrib.get("views") or 0)
                    except ValueError:
                        views = 0
        if not link and video_id:
            link = "https://www.youtube.com/watch?v=" + video_id
        is_short = "/shorts/" in link or "#shorts" in title.lower() or "#short" in title.lower()
        entries.append({
            "videoId": video_id,
            "title": title,
            "url": link,
            "publishedMs": parse_time(published),
            "author": author,
            "thumb": thumb,
            "views": views,
            "excerpt": re.sub(r"\s+", " ", description).strip()[:280],
            "short": is_short,
        })
    return entries


def parse_rss_entries(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    items = (channel.findall("item") if channel is not None else []) or root.findall(f"{ATOM}entry")
    if root.tag.endswith("feed") or root.tag == f"{ATOM}feed":
        return parse_atom_entries(xml_text)
    entries = []
    for item in items:
        title = text_of(child(item, "title"))
        link = text_of(child(item, "link"))
        if not link:
            guid = child(item, "guid")
            link = text_of(guid)
        date = text_of(child(item, "pubDate", "published", "dc:date"))
        desc = text_of(child(item, "description"))
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = unescape(re.sub(r"\s+", " ", desc)).strip()[:280]
        entries.append({
            "title": title,
            "url": link,
            "publishedMs": parse_time(date),
            "excerpt": desc,
            "author": "",
            "thumb": "",
            "views": 0,
            "short": False,
            "videoId": "",
        })
    return entries


def youtube_rss_url(channel_id: str) -> str:
    return "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id


def playlist_rss_url(playlist_id: str) -> str:
    return "https://www.youtube.com/feeds/videos.xml?playlist_id=" + playlist_id


YT_BROWSE = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"
YT_VIDEOS_PARAMS = "EgZ2aWRlb3PyBgQKAjoA"
YT_LIVE_PARAMS = "EgdzdHJlYW1z8gYECgJ6AA=="
YT_CLIENT = {"clientName": "WEB", "clientVersion": "2.20250920.01.00", "hl": "pl", "gl": "PL"}


def http_post_json(url: str, payload: dict, timeout: float = 12) -> dict:
    assert_fetch_url(url, media=False)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": BROWSER_UA,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    opener = urllib.request.build_opener(GuardedRedirectHandler(media=False))
    with opener.open(req, timeout=timeout) as resp:
        body = _read_limited(resp, MAX_DOCUMENT_BYTES)
    return json.loads(body.decode("utf-8", "replace"))


def youtube_browse(browse_id: str, params: str = "") -> dict:
    body = {"context": {"client": YT_CLIENT}, "browseId": browse_id}
    if params:
        body["params"] = params
    return http_post_json(YT_BROWSE, body)


def _walk_lockups(node) -> list:
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            lockup = obj.get("lockupViewModel")
            if isinstance(lockup, dict) and lockup.get("contentId"):
                found.append(lockup)
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(node)
    return found


def _badge_texts(lockup: dict) -> list[str]:
    texts = []

    def walk(obj):
        if isinstance(obj, dict):
            badge = obj.get("thumbnailBadgeViewModel")
            if isinstance(badge, dict) and badge.get("text"):
                texts.append(str(badge["text"]))
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(lockup.get("contentImage") or {})
    return texts


def _meta_parts(lockup: dict) -> list[str]:
    meta = ((lockup.get("metadata") or {}).get("lockupMetadataViewModel") or {})
    rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or [])
    parts = []
    for row in rows:
        for part in row.get("metadataParts") or []:
            text = ((part.get("text") or {}).get("content") or "").strip()
            if text:
                parts.append(text)
    return parts


def _polish_views(text: str) -> int:
    raw = (text or "").replace("\xa0", " ").lower()
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(tysi[aą]ce|tys|mln|mld)?", raw)
    if not match or "wyświetl" not in raw:
        return 0
    number = float(match.group(1).replace(",", "."))
    unit = match.group(2) or ""
    scale = 1
    if unit.startswith("tys"):
        scale = 1000
    elif unit == "mln":
        scale = 1000000
    elif unit == "mld":
        scale = 1000000000
    return int(number * scale)


def _polish_time_ms(text: str) -> int:
    raw = (text or "").replace("\xa0", " ").lower()
    raw = raw.replace("transmisja odbyła się", "").strip()
    dated = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:,\s*(\d{1,2}):(\d{2}))?", raw)
    if dated:
        day, month, year = int(dated.group(1)), int(dated.group(2)), int(dated.group(3))
        hour = int(dated.group(4) or 0)
        minute = int(dated.group(5) or 0)
        try:
            when = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        except ValueError:
            return 0
        return int(when.timestamp() * 1000)
    match = re.search(
        r"(\d+)\s*(sekund|minut|godzin|dzień|dzien|dni|tydzień|tydzien|tygodnie|tygodni|miesiąc|miesiac|miesiące|miesiace|miesięcy|miesiecy|rok|lata|lat)\b",
        raw,
    )
    if not match:
        return 0
    count = int(match.group(1))
    unit = match.group(2)
    seconds = count
    if unit.startswith("minut"):
        seconds = count * 60
    elif unit.startswith("godzin"):
        seconds = count * 3600
    elif unit.startswith("dzie") or unit == "dni":
        seconds = count * 86400
    elif unit.startswith("tydz"):
        seconds = count * 7 * 86400
    elif unit.startswith("mies"):
        seconds = count * 30 * 86400
    elif unit in ("rok", "lata", "lat"):
        seconds = count * 365 * 86400
    return now_ms() - seconds * 1000


def _duration_seconds(text: str) -> int:
    parts = [int(piece) for piece in re.findall(r"\d+", text or "")]
    if not parts or len(parts) > 3:
        return 0
    seconds = 0
    for piece in parts:
        seconds = seconds * 60 + piece
    return seconds


def parse_lockups(data: dict, short: bool = False) -> list[dict]:
    entries = []
    seen = set()
    for lockup in _walk_lockups(data):
        if lockup.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
            continue
        video_id = str(lockup.get("contentId") or "")
        if not re.fullmatch(r"[\w-]{11}", video_id) or video_id in seen:
            continue
        seen.add(video_id)
        meta = (lockup.get("metadata") or {}).get("lockupMetadataViewModel") or {}
        title = ((meta.get("title") or {}).get("content") or "").strip()
        if not title:
            continue
        parts = _meta_parts(lockup)
        badges = _badge_texts(lockup)
        views = 0
        published = 0
        author = ""
        for part in parts:
            if _polish_views(part):
                views = _polish_views(part)
            elif _polish_time_ms(part):
                published = _polish_time_ms(part)
            elif not author:
                author = part
        duration = _duration_seconds(badges[0] if badges else "")
        badge_blob = " ".join(badges).lower()
        entries.append({
            "title": title,
            "url": "https://www.youtube.com/watch?v=" + video_id,
            "publishedMs": published,
            "excerpt": "",
            "author": author,
            "thumb": "",
            "views": views,
            "short": short or (0 < duration <= 60),
            "videoId": video_id,
            "liveBadge": badge_blob,
        })
    return entries


def youtube_thumb(video_id: str) -> str:
    vid = (video_id or "").strip()
    if not re.fullmatch(r"[\w-]{11}", vid):
        return ""
    return cache_media("https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid)


def item_from_yt(source_id: str, kind: str, raw: dict) -> dict:
    video_id = raw.get("videoId") or ""
    thumb = youtube_thumb(video_id)
    return {
        "id": f"{source_id}:{video_id or raw.get('url')}",
        "videoId": video_id,
        "source": source_id,
        "kind": "short" if raw.get("short") else kind,
        "title": raw.get("title") or "",
        "url": raw.get("url") or "",
        "publishedMs": raw.get("publishedMs") or 0,
        "author": raw.get("author") or "",
        "thumb": thumb,
        "views": raw.get("views") or 0,
        "excerpt": raw.get("excerpt") or "",
        "live": False,
    }


def _yt_from_browse(browse_id: str, params: str = "", short: bool = False) -> list[dict]:
    try:
        data = youtube_browse(browse_id, params)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return []
    return parse_lockups(data, short=short)[:15]


def fetch_youtube_channel(spec: dict) -> tuple[str, dict]:
    entries = _yt_from_browse(spec["channel_id"], YT_VIDEOS_PARAMS)
    if not entries:
        final, body, err = safe_get(youtube_rss_url(spec["channel_id"]), timeout=10)
        if not err and body:
            try:
                entries = parse_atom_entries(body)
            except ET.ParseError:
                entries = []
    if not entries:
        return spec["id"], {"ok": False, "error": "no videos", "items": []}
    items = [item_from_yt(spec["id"], "video", entry) for entry in entries]
    return spec["id"], {"ok": True, "items": items, "url": spec["url"]}


def fetch_guest_playlist(spec: dict) -> tuple[str, dict]:
    entries = _yt_from_browse("VL" + spec["playlist_id"])
    if not entries:
        final, body, err = safe_get(playlist_rss_url(spec["playlist_id"]), timeout=10)
        if not err and body:
            try:
                entries = parse_atom_entries(body)
            except ET.ParseError:
                entries = []
    if not entries:
        return spec["id"], {"ok": False, "error": "no videos", "items": []}
    items = [item_from_yt(spec["id"], "guest", entry) for entry in entries]
    return spec["id"], {"ok": True, "items": items, "url": spec["url"]}


def check_live(spec: dict) -> dict | None:
    channel_id = spec.get("channel_id")
    if not channel_id:
        return None
    for entry in _yt_from_browse(channel_id, YT_LIVE_PARAMS):
        badge = entry.get("liveBadge") or ""
        is_live = "na żywo" in badge or "live" in badge
        is_upcoming = "wkrótce" in badge or "upcoming" in badge
        if not is_live and not is_upcoming:
            continue
        video_id = entry["videoId"]
        return {
            "id": f"live:{spec['id']}:{video_id}",
            "source": spec["id"],
            "kind": "live" if is_live else "upcoming",
            "title": entry["title"],
            "url": entry["url"],
            "publishedMs": entry.get("publishedMs") or now_ms(),
            "author": spec["label"],
            "thumb": cache_media(f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"),
            "views": entry.get("views") or 0,
            "excerpt": "",
            "live": is_live,
        }
    return None


def parse_patronite(html: str) -> dict:
    def first_stat(key: str) -> int | None:
        m = re.search(r'id="stats-%s">\s*([^<]+)' % re.escape(key), html)
        if not m:
            return None
        digits = re.sub(r"[^\d]", "", m.group(1))
        return int(digits) if digits else None

    return {
        "url": "https://patronite.pl/tetrycy",
        "patrons": first_stat("patrons"),
        "monthly": first_stat("monthly"),
        "total": first_stat("total"),
    }


def fetch_patronite() -> dict:
    final, body, err = safe_get("https://patronite.pl/tetrycy", timeout=8, browser=True)
    if err or not body:
        return {"ok": False, "error": err or "empty"}
    stats = parse_patronite(body)
    stats["ok"] = stats.get("patrons") is not None or stats.get("monthly") is not None
    if not stats["ok"]:
        stats["error"] = "parse"
    return stats


def fetch_fxtwitter(account: dict) -> dict:
    url = "https://api.fxtwitter.com/" + urllib.parse.quote(account["handle"])
    final, body, err = safe_get(url, timeout=6, browser=True)
    profile = {
        "id": account["id"],
        "source": account["id"],
        "kind": "profile",
        "label": account["label"],
        "handle": account["handle"],
        "url": "https://x.com/" + account["handle"],
        "ok": False,
    }
    if err or not body:
        # Keep the profile row even when the unofficial API is down.
        profile["error"] = err or "empty"
        profile["ok"] = True
        profile["name"] = account["label"]
        return profile
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        profile["error"] = "parse"
        return profile
    user = data.get("user") or data
    profile.update({
        "ok": True,
        "name": user.get("name") or account["label"],
        "bio": user.get("description") or "",
        "followers": user.get("followers") or user.get("followers_count") or 0,
        "tweets": user.get("tweets") or user.get("statuses_count") or 0,
    })
    return profile


def _itemprop(block: str, name: str) -> str:
    pat = r'(?:itemProp="%s"[^>]*content="([^"]*)"|content="([^"]*)"[^>]*itemProp="%s")' % (
        re.escape(name),
        re.escape(name),
    )
    m = re.search(pat, block, re.I | re.S)
    if not m:
        return ""
    return unescape((m.group(1) or m.group(2) or "").replace("\r", "").strip())


def shrink_twimg(url: str) -> str:
    if not url or "pbs.twimg.com" not in url:
        return url
    href = url.replace("format=webp", "format=jpg").replace(".webp", ".jpg")
    if "name=" in href:
        href = re.sub(r"name=[^&]+", "name=small", href)
    else:
        href += ("&" if "?" in href else "?") + "name=small"
    if "format=" not in href:
        href += "&format=jpg"
    return href


def _tweet_stub(account: dict, tweet_id: str, text: str = "", published: str = "", photos: list | None = None) -> dict:
    photos = photos or []
    return {
        "id": "%s:%s" % (account["id"], tweet_id),
        "tweetId": tweet_id,
        "source": account["id"],
        "kind": "post",
        "title": text,
        "url": "https://x.com/%s/status/%s" % (account["handle"], tweet_id),
        "publishedMs": parse_time(published),
        "author": account["label"],
        "authorName": account["label"],
        "handle": account["handle"],
        "avatar": "",
        "photos": photos,
        "thumb": (photos[0]["url"] if photos else ""),
        "likes": 0,
        "retweets": 0,
        "replies": 0,
        "views": 0,
        "excerpt": text,
        "live": False,
    }


def parse_x_profile(html: str, account: dict) -> list[dict]:
    items = []
    seen = set()
    handle = re.escape(account["handle"])

    for m in re.finditer(r"<article\b([^>]*)>(.*?)</article>", html, re.I | re.S):
        attrs, inner = m.group(1), m.group(2)
        tweet_id = ""
        id_attr = re.search(r'data-tweet-id="(\d+)"', attrs, re.I)
        if id_attr:
            tweet_id = id_attr.group(1)
        if not tweet_id:
            tweet_id = _itemprop(inner, "identifier")
        if not tweet_id:
            id_url = re.search(r'itemID="https://x\.com/(?:i|[^/]+)/status/(\d+)"', attrs, re.I)
            if id_url:
                tweet_id = id_url.group(1)
        if not tweet_id:
            href_id = re.search(r'href="/(?:i|%s)/status/(\d+)"' % handle, inner, re.I)
            if href_id:
                tweet_id = href_id.group(1)
        if not tweet_id.isdigit() or tweet_id in seen:
            continue
        seen.add(tweet_id)
        text = re.sub(r"\s+", " ", _itemprop(inner, "text")).strip()
        published = _itemprop(inner, "datePublished") or _itemprop(inner, "dateCreated")
        photos = []
        for img in re.finditer(
            r'<img\b[^>]*src="(https://pbs\.twimg\.com/media/[^"]+)"[^>]*>',
            inner,
            re.I,
        ):
            href = shrink_twimg(unescape(img.group(1)))
            w = re.search(r'\bwidth="(\d+)"', img.group(0))
            h = re.search(r'\bheight="(\d+)"', img.group(0))
            photos.append({
                "url": href,
                "width": int(w.group(1)) if w else 16,
                "height": int(h.group(1)) if h else 9,
            })
        items.append(_tweet_stub(account, tweet_id, text, published, photos))

    # Current x.com profile HTML dropped schema.org cards; tweet ids still
    # appear as /handle/status/<id> links. Stubs are filled by FixTweet.
    for tweet_id in re.findall(r'href="/(?:i|%s)/status/(\d+)"' % handle, html, re.I):
        if tweet_id in seen:
            continue
        seen.add(tweet_id)
        items.append(_tweet_stub(account, tweet_id))
    return items


def enrich_fx_tweet(item: dict, account: dict) -> dict:
    tweet_id = str(item.get("tweetId") or "")
    if not tweet_id.isdigit():
        return item
    url = "https://api.fxtwitter.com/%s/status/%s" % (account["handle"], tweet_id)
    final, body, err = safe_get(url, timeout=8, browser=True)
    if err or not body:
        return item
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return item
    tweet = data.get("tweet") or {}
    author = tweet.get("author") or {}
    media = tweet.get("media") or {}
    photos = []
    for photo in media.get("photos") or []:
        href = photo.get("url") or ""
        if href:
            photos.append({
                "url": shrink_twimg(href),
                "width": int(photo.get("width") or 16),
                "height": int(photo.get("height") or 9),
            })
    if not photos:
        for extra in media.get("all") or []:
            href = extra.get("thumbnail_url") or extra.get("url") or ""
            if href and extra.get("type") in ("photo", "gif", "video"):
                photos.append({
                    "url": shrink_twimg(href),
                    "width": int(extra.get("width") or 16),
                    "height": int(extra.get("height") or 9),
                })
    if not photos:
        card = tweet.get("twitter_card") or {}
        if isinstance(card, dict):
            href = card.get("image") or ""
            if isinstance(href, dict):
                href = href.get("url") or href.get("src") or ""
            if href:
                photos.append({"url": shrink_twimg(str(href)), "width": 16, "height": 9})
    text = (tweet.get("text") or item.get("title") or "").strip()
    ts = tweet.get("created_timestamp")
    local_photos = localize_photos(photos or item.get("photos") or [])
    item.update({
        "title": text or item.get("title"),
        "excerpt": text or item.get("excerpt"),
        "url": item.get("url") or ("https://x.com/%s/status/%s" % (account["handle"], tweet_id)),
        "author": author.get("name") or item.get("author"),
        "authorName": author.get("name") or item.get("authorName"),
        "handle": author.get("screen_name") or account["handle"],
        "avatar": cache_media(author.get("avatar_url") or item.get("avatar") or ""),
        "photos": local_photos,
        "thumb": (local_photos[0].get("url") if local_photos else ""),
        "likes": tweet.get("likes") or 0,
        "retweets": tweet.get("retweets") or 0,
        "replies": tweet.get("replies") or 0,
        "views": tweet.get("views") or item.get("views") or 0,
    })
    if ts:
        try:
            item["publishedMs"] = int(ts) * 1000
        except (TypeError, ValueError):
            pass
    return item


def fetch_x_tweets(account: dict) -> list[dict]:
    url = "https://x.com/" + account["handle"]
    final, body, err = safe_get(url, timeout=12, browser=True)
    if err or not body:
        return fetch_nitter_rss(account)
    items = parse_x_profile(body, account)[:8]
    if not items:
        return fetch_nitter_rss(account)
    with ThreadPoolExecutor(max_workers=6) as pool:
        enriched = list(pool.map(lambda item: enrich_fx_tweet(item, account), items))
    return [item for item in enriched if item.get("title") or item.get("excerpt")]


def fetch_nitter_rss(account: dict) -> list[dict]:
    for template in NITTER_RSS:
        url = template.format(handle=account["handle"])
        final, body, err = safe_get(url, timeout=4, browser=True)
        if err or not body or "<rss" not in body[:400] and "<feed" not in body[:400]:
            continue
        try:
            if "<feed" in body[:400]:
                raw_items = parse_atom_entries(body)
            else:
                raw_items = parse_rss_entries(body)
        except ET.ParseError:
            continue
        items = []
        for raw in raw_items[:8]:
            title = raw.get("title") or raw.get("excerpt") or ""
            if not title:
                continue
            items.append({
                "id": f"{account['id']}:{raw.get('url') or title}",
                "source": account["id"],
                "kind": "post",
                "title": title,
                "url": raw.get("url") or ("https://x.com/" + account["handle"]),
                "publishedMs": raw.get("publishedMs") or 0,
                "author": account["label"],
                "thumb": "",
                "views": 0,
                "excerpt": raw.get("excerpt") or "",
                "live": False,
            })
        if items:
            return items
    return []


def build_bundle() -> dict:
    errors: dict[str, str] = {}
    items: list[dict] = []
    live: list[dict] = []
    profiles: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for spec in CHANNELS.values():
            futures[pool.submit(fetch_youtube_channel, spec)] = ("yt", spec["id"])
            futures[pool.submit(check_live, spec)] = ("live", spec["id"])
        for spec in GUESTS.values():
            futures[pool.submit(fetch_guest_playlist, spec)] = ("guest", spec["id"])
        futures[pool.submit(fetch_patronite)] = ("patronite", "patronite")
        for account in X_ACCOUNTS:
            futures[pool.submit(fetch_fxtwitter, account)] = ("x-profile", account["id"])
            futures[pool.submit(fetch_x_tweets, account)] = ("x-rss", account["id"])

        patronite = {"ok": False}
        for fut in as_completed(futures):
            kind, source_id = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                errors[source_id] = str(exc)
                continue
            if kind in ("yt", "guest"):
                _sid, payload = result
                if not payload.get("ok"):
                    errors[source_id] = payload.get("error") or "fail"
                items.extend(payload.get("items") or [])
            elif kind == "live":
                if result:
                    live.append(result)
                    items.append(result)
            elif kind == "patronite":
                patronite = result
                if not result.get("ok"):
                    errors["patronite"] = result.get("error") or "fail"
            elif kind == "x-profile":
                profiles.append(result)
                if not result.get("ok"):
                    errors[source_id] = result.get("error") or "fail"
            elif kind == "x-rss":
                items.extend(result or [])

    items.sort(key=lambda it: it.get("publishedMs") or 0, reverse=True)
    # Keep the feed from growing without bound; the panel shows a window of this.
    items = items[:60]
    live.sort(key=lambda it: 0 if it.get("live") else 1)

    return {
        "ok": True,
        "fetchedAt": now_ms(),
        "items": items,
        "live": live,
        "profiles": profiles,
        "links": LINKS,
        "patronite": patronite,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--prepare-state", action="store_true")
    parser.add_argument("--write-state", choices=["cache", "seen"])
    args = parser.parse_args()
    if args.prepare_state or args.write_state:
        try:
            if args.write_state:
                write_state_file(args.write_state, sys.stdin.buffer.read())
            else:
                ensure_state_tree()
        except OSError:
            return 2
        return 0
    try:
        bundle = build_bundle()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, RuntimeError) as exc:
        json.dump({"ok": False, "error": str(exc), "fetchedAt": now_ms()}, sys.stdout)
        return 1
    json.dump(bundle, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
