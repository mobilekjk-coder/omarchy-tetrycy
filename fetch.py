#!/usr/bin/env python3
"""Pull a Tetrycy bundle for the Omarchy widget.

YouTube RSS is the reliable source.
X posts come from the public profile pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def http_get(url: str, timeout: float = 8, browser: bool = False, headers: dict | None = None) -> tuple[str, str]:
    hdrs = {
        "User-Agent": BROWSER_UA if browser else UA,
        "Accept": "*/*",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl(), resp.read().decode("utf-8", "replace")


def cache_media(url: str) -> str:
    href = (url or "").strip()
    if not href:
        return ""
    if href.startswith("file:"):
        return href
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(href.encode("utf-8", "replace")).hexdigest()[:20]
    path = MEDIA_DIR / (digest + ".jpg")
    if path.is_file() and path.stat().st_size > 200:
        return path.as_uri()
    try:
        hdrs = {"User-Agent": BROWSER_UA, "Accept": "image/*,*/*"}
        req = urllib.request.Request(href, headers=hdrs)
        with urllib.request.urlopen(req, timeout=8) as resp:
            blob = resp.read()
        if not blob:
            return href
        path.write_bytes(blob)
        return path.as_uri()
    except Exception:
        return href


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


def youtube_thumb(video_id: str) -> str:
    vid = (video_id or "").strip()
    if not vid:
        return ""
    return cache_media("https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid)


def item_from_yt(source_id: str, kind: str, raw: dict) -> dict:
    video_id = raw.get("videoId") or ""
    thumb = youtube_thumb(video_id) or raw.get("thumb") or ""
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


def fetch_youtube_channel(spec: dict) -> tuple[str, dict]:
    url = youtube_rss_url(spec["channel_id"])
    final, body, err = safe_get(url, timeout=10)
    if err or not body:
        return spec["id"], {"ok": False, "error": err or "empty", "items": []}
    try:
        entries = parse_atom_entries(body)
    except ET.ParseError as exc:
        return spec["id"], {"ok": False, "error": str(exc), "items": []}
    items = [item_from_yt(spec["id"], "video", e) for e in entries]
    return spec["id"], {"ok": True, "items": items, "url": spec["url"]}


def fetch_guest_playlist(spec: dict) -> tuple[str, dict]:
    url = playlist_rss_url(spec["playlist_id"])
    final, body, err = safe_get(url, timeout=10)
    if err or not body:
        return spec["id"], {"ok": False, "error": err or "empty", "items": []}
    try:
        entries = parse_atom_entries(body)
    except ET.ParseError as exc:
        return spec["id"], {"ok": False, "error": str(exc), "items": []}
    items = [item_from_yt(spec["id"], "guest", e) for e in entries]
    return spec["id"], {"ok": True, "items": items, "url": spec["url"]}


def check_live(spec: dict) -> dict | None:
    handle = spec.get("handle")
    if not handle:
        return None
    url = f"https://www.youtube.com/@{handle}/live"
    final, body, err = safe_get(url, timeout=8, browser=True)
    if err or not body:
        return None
    video_id = ""
    if final:
        m = re.search(r"[?&]v=([\w-]{11})", final)
        if m:
            video_id = m.group(1)
    if not video_id:
        m = re.search(r'rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', body)
        if m:
            video_id = m.group(1)
    if not video_id:
        return None
    compact = body.replace(" ", "")
    is_live = '"isLive":true' in compact or '"isLiveNow":true' in compact
    is_upcoming = '"isUpcoming":true' in compact
    if not is_live and not is_upcoming:
        return None
    title = ""
    tm = re.search(r'"videoDetails"\s*:\s*\{[^{}]{0,800}?"title"\s*:\s*"((?:\\.|[^"\\])*)"', body)
    if tm:
        title = tm.group(1).encode("utf-8").decode("unicode_escape")
    if not title:
        og = re.search(r'<meta property="og:title" content="([^"]+)"', body)
        title = unescape(og.group(1)) if og else spec["label"]
    return {
        "id": f"live:{spec['id']}:{video_id}",
        "source": spec["id"],
        "kind": "live" if is_live else "upcoming",
        "title": title,
        "url": "https://www.youtube.com/watch?v=" + video_id,
        "publishedMs": now_ms(),
        "author": spec["label"],
        "thumb": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "views": 0,
        "excerpt": "",
        "live": is_live,
    }


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


def parse_x_profile(html: str, account: dict) -> list[dict]:
    items = []
    seen = set()
    for m in re.finditer(
        r'<article[^>]*data-tweet-id="(\d+)"[^>]*>(.*?)</article>',
        html,
        re.I | re.S,
    ):
        tweet_id, inner = m.group(1), m.group(2)
        if tweet_id in seen:
            continue
        seen.add(tweet_id)
        text = re.sub(r"\s+", " ", _itemprop(inner, "text")).strip()
        if not text:
            continue
        url = _itemprop(inner, "url") or ("https://x.com/%s/status/%s" % (account["handle"], tweet_id))
        published = _itemprop(inner, "datePublished") or _itemprop(inner, "dateCreated")
        photos = []
        for img in re.findall(r'src="(https://pbs\.twimg\.com/media/[^"]+)"', inner):
            photos.append({"url": shrink_twimg(unescape(img)), "width": 16, "height": 9})
        items.append({
            "id": "%s:%s" % (account["id"], tweet_id),
            "tweetId": tweet_id,
            "source": account["id"],
            "kind": "post",
            "title": text,
            "url": url,
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
        })
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
        "url": tweet.get("url") or item.get("url"),
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
        return list(pool.map(lambda item: enrich_fx_tweet(item, account), items))


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
    args = parser.parse_args()
    try:
        bundle = build_bundle()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, RuntimeError) as exc:
        json.dump({"ok": False, "error": str(exc), "fetchedAt": now_ms()}, sys.stdout)
        return 1
    json.dump(bundle, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
