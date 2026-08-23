// Normalized Tetrycy bundle. fetch.py is the only I/O; this file is pure.
// Copy is Polish-only — Tetrycy publish in Polish.

var FILTERS = ["all", "tetrycy", "forte", "betclic", "x"]

var STRINGS = {
  all: "WSZYSTKO",
  tetrycy: "TETRYCY",
  forte: "FORTE",
  betclic: "GOŚCIE",
  x: "X",
  leszek: "LESZEK",
  olki: "OLKI",
  live: "NA ŻYWO",
  liveShort: "NA ŻYWO",
  upcoming: "WKRÓTCE",
  latest: "NAJNOWSZE",
  links: "LINKI",
  patrons: "patronów",
  loading: "Ładowanie…",
  empty: "Nic tu nie ma. Odśwież, albo otwórz źródło poniżej.",
  error: "Część źródeł nie odpowiedziała.",
  now: "teraz",
  min: "min",
  hour: "godz.",
  day: "dni",
  notifyTitle: "Tetrycy",
  close: "ZAMKNIJ"
}

function t(key) {
  return STRINGS[key] || key
}

function emptySnapshot() {
  return {
    ok: false,
    fetchedAt: 0,
    items: [],
    live: [],
    profiles: [],
    links: [],
    patronite: {},
    errors: {}
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {}
}

function normalizePhoto(entry) {
  if (!entry) return null
  if (typeof entry === "string") return { url: entry, width: 16, height: 9 }
  var href = String(entry.url || "")
  if (!href) return null
  return {
    url: href,
    width: Math.max(1, Number(entry.width) || 16),
    height: Math.max(1, Number(entry.height) || 9)
  }
}

function firstPhoto(item) {
  var photos = item && item.photos
  return photos && photos.length ? photos[0] : null
}

function photoUrl(item) {
  var photo = firstPhoto(item)
  if (!photo) return ""
  return typeof photo === "string" ? photo : String(photo.url || "")
}

function photoHeightForWidth(item, width, maxHeight) {
  var photo = firstPhoto(item)
  if (!photo) return 0
  var w = Math.max(1, Number(photo.width) || 16)
  var h = Math.max(1, Number(photo.height) || 9)
  var scaled = Math.round(Number(width) * h / w)
  var cap = maxHeight || 510
  if (scaled < 1) return 0
  return scaled > cap ? cap : scaled
}

function normalizeItem(raw) {
  if (!raw || typeof raw !== "object") return null
  var title = String(raw.title || "").replace(/^\s+|\s+$/g, "")
  var url = String(raw.url || "")
  if (!title && !url) return null
  var photos = []
  var rawPhotos = raw.photos
  if (Array.isArray(rawPhotos)) {
    for (var i = 0; i < rawPhotos.length; i++) {
      var photo = normalizePhoto(rawPhotos[i])
      if (photo) photos.push(photo)
    }
  } else if (raw.thumb) {
    var thumbPhoto = normalizePhoto(raw.thumb)
    if (thumbPhoto) photos.push(thumbPhoto)
  }
  return {
    id: String(raw.id || url || title),
    source: String(raw.source || ""),
    kind: String(raw.kind || "video"),
    title: title,
    url: url,
    publishedMs: Number(raw.publishedMs) || 0,
    author: String(raw.author || ""),
    authorName: String(raw.authorName || raw.author || ""),
    handle: String(raw.handle || ""),
    avatar: String(raw.avatar || ""),
    photos: photos,
    thumb: String(raw.thumb || (photos.length ? photos[0].url : "")),
    likes: Number(raw.likes) || 0,
    retweets: Number(raw.retweets) || 0,
    replies: Number(raw.replies) || 0,
    views: Number(raw.views) || 0,
    excerpt: String(raw.excerpt || ""),
    live: raw.live === true,
    videoId: String(raw.videoId || "")
  }
}

function formatViews(value) {
  var n = Number(value) || 0
  if (n >= 1000000) return (Math.round(n / 100000) / 10) + " mln"
  if (n >= 1000) return Math.round(n / 1000) + " tys."
  return String(n)
}

function youtubeThumb(item) {
  if (!item) return ""
  if (item.thumb) return String(item.thumb)
  if (item.videoId) return "https://i.ytimg.com/vi/" + item.videoId + "/mqdefault.jpg"
  return ""
}

function parseBundle(raw, nowMs) {
  var data = asObject(raw)
  var items = []
  var seen = {}
  var list = asArray(data.items)
  for (var i = 0; i < list.length; i++) {
    var item = normalizeItem(list[i])
    if (!item || seen[item.id]) continue
    seen[item.id] = true
    items.push(item)
  }
  items.sort(function(a, b) {
    return (b.publishedMs || 0) - (a.publishedMs || 0)
  })
  var live = []
  var liveRaw = asArray(data.live)
  for (var j = 0; j < liveRaw.length; j++) {
    var liveItem = normalizeItem(liveRaw[j])
    if (liveItem) live.push(liveItem)
  }
  return {
    ok: data.ok !== false,
    fetchedAt: Number(data.fetchedAt) || nowMs || 0,
    items: items,
    live: live,
    profiles: asArray(data.profiles),
    links: asArray(data.links),
    patronite: asObject(data.patronite),
    errors: asObject(data.errors)
  }
}

function parseCache(text, nowMs) {
  try {
    return parseBundle(JSON.parse(String(text || "{}")), nowMs)
  } catch (e) {
    return emptySnapshot()
  }
}

function liveNow(snapshot) {
  var list = snapshot && snapshot.live ? snapshot.live : []
  for (var i = 0; i < list.length; i++) {
    if (list[i] && (list[i].live || list[i].kind === "live")) return list[i]
  }
  return null
}

function latestItem(snapshot, showShorts) {
  var list = snapshot && snapshot.items ? snapshot.items : []
  for (var i = 0; i < list.length; i++) {
    var item = list[i]
    if (!item) continue
    if (!showShorts && item.kind === "short") continue
    if (item.kind === "profile" || item.kind === "post") continue
    return item
  }
  return null
}

function sourceMatches(item, filter) {
  if (!item) return false
  if (filter === "all" || !filter) return true
  if (filter === "tetrycy") return item.source === "tetrycy"
  if (filter === "forte") return item.source === "forte"
  if (filter === "betclic") return item.source === "betclic" || item.kind === "guest"
  if (filter === "x") return item.source.indexOf("x-") === 0
  return item.source === filter
}

function filteredItems(snapshot, filter, showShorts, limit) {
  var list = snapshot && snapshot.items ? snapshot.items : []
  var out = []
  var cap = limit || 22
  for (var i = 0; i < list.length && out.length < cap; i++) {
    var item = list[i]
    if (!showShorts && item.kind === "short") continue
    if (item.kind === "live") continue
    if (filter !== "x" && item.kind === "post") continue
    if (!sourceMatches(item, filter)) continue
    out.push(item)
  }
  return out
}

function sourceBadge(item) {
  if (!item) return ""
  if (item.kind === "live") return "LIVE"
  if (item.source === "tetrycy") return "YT"
  if (item.source === "forte") return "FORTE"
  if (item.source === "betclic") return "BETCLIC"
  if (item.source === "x-leszek") return "LESZEK"
  if (item.source === "x-kuba") return "OLKI"
  return (item.source || "").toUpperCase()
}

function formatAgo(ms, nowMs) {
  if (!ms) return ""
  var delta = Math.max(0, (nowMs || Date.now()) - ms)
  var minutes = Math.floor(delta / 60000)
  if (minutes < 1) return t("now")
  if (minutes < 60) return minutes + " " + t("min")
  var hours = Math.floor(minutes / 60)
  if (hours < 24) return hours + " " + t("hour")
  var days = Math.floor(hours / 24)
  if (days < 8) return days + " " + t("day")
  var d = new Date(ms)
  var dd = d.getDate()
  var mm = d.getMonth() + 1
  return (dd < 10 ? "0" : "") + dd + "." + (mm < 10 ? "0" : "") + mm
}

function truncate(text, max) {
  var value = String(text || "")
  if (value.length <= max) return value
  return value.slice(0, Math.max(0, max - 1)).replace(/\s+\S*$/, "") + "…"
}

function barLabel(snapshot, nowMs, showShorts) {
  var live = liveNow(snapshot)
  if (live) return t("liveShort")
  var latest = latestItem(snapshot, showShorts)
  if (!latest) return "TETRYCY"
  var ago = formatAgo(latest.publishedMs, nowMs)
  var title = truncate(latest.title, 28)
  if (!title) return "TETRYCY"
  return title + (ago ? " · " + ago : "")
}

function barLabelVertical(snapshot, showShorts) {
  if (liveNow(snapshot)) return "NA ŻYWO"
  var latest = latestItem(snapshot, showShorts)
  if (!latest) return "TET\n—"
  return "TET\n" + formatAgo(latest.publishedMs, Date.now())
}

function patronLine(patronite) {
  var patrons = asObject(patronite).patrons
  if (!patrons) return ""
  return formatNumber(patrons) + " " + t("patrons")
}

function patronLink(snapshot) {
  var links = snapshot && snapshot.links ? snapshot.links : []
  for (var i = 0; i < links.length; i++) {
    if (links[i] && links[i].id === "patronite") return links[i]
  }
  return { id: "patronite", title: "Patronite", url: "https://patronite.pl/tetrycy" }
}

function formatNumber(value) {
  var n = Number(value)
  if (!isFinite(n)) return String(value || "")
  var s = String(Math.round(n))
  var out = ""
  while (s.length > 3) {
    out = " " + s.slice(-3) + out
    s = s.slice(0, -3)
  }
  return s + out
}

function notifySummary(item) {
  if (!item) return t("notifyTitle")
  if (item.live || item.kind === "live") return t("live") + " · " + t("notifyTitle")
  return t("notifyTitle")
}

function notifyBody(item) {
  if (!item) return ""
  return item.title || item.url || ""
}

function newItems(snapshot, seenIds, showShorts) {
  var known = asObject(seenIds)
  var out = []
  var list = snapshot && snapshot.items ? snapshot.items : []
  for (var i = 0; i < list.length; i++) {
    var item = list[i]
    if (!item || known[item.id]) continue
    if (!showShorts && item.kind === "short") continue
    if (item.kind === "video" || item.kind === "guest" || item.kind === "live" || item.kind === "short")
      out.push(item)
  }
  return out
}

function collectSeen(snapshot) {
  var ids = {}
  var list = snapshot && snapshot.items ? snapshot.items : []
  for (var i = 0; i < list.length; i++) {
    if (list[i] && list[i].id) ids[list[i].id] = true
  }
  return ids
}

function hasErrors(snapshot) {
  var errors = snapshot && snapshot.errors ? snapshot.errors : {}
  for (var key in errors) {
    if (errors[key]) return true
  }
  return false
}

function xProfiles(snapshot) {
  var list = snapshot && snapshot.profiles ? snapshot.profiles : []
  var out = []
  for (var i = 0; i < list.length; i++) {
    if (list[i] && String(list[i].source || list[i].id || "").indexOf("x-") === 0)
      out.push(list[i])
  }
  return out
}

function tweetItems(snapshot, limit) {
  return tweetItemsFor(snapshot, "", limit)
}

function tweetItemsFor(snapshot, sourceId, limit) {
  var list = snapshot && snapshot.items ? snapshot.items : []
  var out = []
  var cap = limit || 16
  var want = String(sourceId || "")
  for (var i = 0; i < list.length && out.length < cap; i++) {
    var item = list[i]
    if (!item || item.kind !== "post") continue
    if (want && item.source !== want) continue
    out.push(item)
  }
  return out
}

function videoItems(snapshot, filter, showShorts, limit) {
  if (filter === "x") return []
  return filteredItems(snapshot, filter, showShorts, limit)
}

function footerLinks(snapshot) {
  var links = snapshot && snapshot.links ? snapshot.links : []
  if (!links.length) {
    links = [
      { id: "youtube", title: "YouTube", url: "https://www.youtube.com/@Tetrycy" },
      { id: "site", title: "tetrycy.com.pl", url: "https://www.tetrycy.com.pl/" }
    ]
  }
  var out = []
  for (var i = 0; i < links.length; i++) {
    if (links[i] && links[i].id !== "patronite") out.push(links[i])
  }
  return out
}
