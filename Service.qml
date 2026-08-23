import QtQuick
import Quickshell
import Quickshell.Io
import "Model.js" as Model

Item {
  id: root

  property var shell: null
  property var manifest: null
  property int refreshMinutes: 10
  property bool showShorts: true
  property bool notifyNew: true
  property var snapshot: Model.emptySnapshot()
  property bool loading: false
  property var seenIds: ({})
  property bool seenReady: false

  readonly property string pluginDir: {
    var url = String(Qt.resolvedUrl("."))
    return url.replace(/^file:\/\//, "").replace(/\/$/, "")
  }
  readonly property string cachePath: Quickshell.env("HOME") + "/.local/state/omarchy/kjk.tetrycy/cache.json"
  readonly property string seenPath: Quickshell.env("HOME") + "/.local/state/omarchy/kjk.tetrycy/seen.json"
  readonly property var nowMs: clock.date.getTime()
  readonly property var live: Model.liveNow(snapshot)
  readonly property bool hasLive: !!live
  readonly property var latest: Model.latestItem(snapshot, showShorts)
  readonly property string label: Model.barLabel(snapshot, nowMs, showShorts)
  readonly property string labelVertical: Model.barLabelVertical(snapshot, showShorts)

  function applyBundle(raw) {
    var parsed = Model.parseBundle(JSON.parse(String(raw || "{}")), Date.now())
    if (parsed.ok) {
      maybeNotify(parsed)
      root.snapshot = parsed
      cacheFile.setText(JSON.stringify(parsed) + "\n")
      seedSeen(parsed)
    } else if (!root.snapshot.ok) {
      root.snapshot = parsed
    }
  }

  function seenCount() {
    var n = 0
    for (var key in root.seenIds) n++
    return n
  }

  function seedSeen(parsed) {
    if (!root.seenReady) return
    if (root.seenCount() > 0) return
    var nextSeen = Model.collectSeen(parsed || root.snapshot)
    root.seenIds = nextSeen
    seenFile.setText(JSON.stringify(nextSeen) + "\n")
  }

  function maybeNotify(parsed) {
    if (!root.notifyNew || !root.seenReady) return
    if (root.seenCount() === 0) return
    var fresh = Model.newItems(parsed, root.seenIds, root.showShorts)
    var nextSeen = Model.collectSeen(parsed)
    root.seenIds = nextSeen
    seenFile.setText(JSON.stringify(nextSeen) + "\n")
    if (!fresh.length) return
    notifyItem(fresh[0])
  }

  function notifyItem(item) {
    if (!item) return
    Quickshell.execDetached(["omarchy-notification-send", Model.notifySummary(item), Model.notifyBody(item)])
  }

  function notifyLatest() {
    notifyItem(root.live || root.latest)
  }

  function refresh() {
    if (fetchProc.running) fetchProc.running = false
    root.loading = true
    fetchProc.command = ["python3", root.pluginDir + "/fetch.py"]
    fetchProc.running = true
  }

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
  }

  FileView {
    id: cacheFile
    path: root.cachePath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var cached = Model.parseCache(text(), Date.now())
      if (cached.ok) root.snapshot = cached
    }
  }

  FileView {
    id: seenFile
    path: root.seenPath
    watchChanges: false
    printErrors: false
    onLoaded: {
      try {
        root.seenIds = JSON.parse(String(text() || "{}"))
      } catch (e) {
        root.seenIds = {}
      }
      root.seenReady = true
      root.seedSeen(root.snapshot)
    }
    onLoadFailed: {
      root.seenIds = {}
      root.seenReady = true
      root.seedSeen(root.snapshot)
    }
  }

  Process {
    id: mkdirProc
    command: ["mkdir", "-p", Quickshell.env("HOME") + "/.local/state/omarchy/kjk.tetrycy"]
  }

  Process {
    id: fetchProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.loading = false
        var raw = String(text || "").trim()
        if (!raw) return
        try {
          root.applyBundle(raw)
        } catch (e) {}
      }
    }
    onExited: function(exitCode) {
      if (root.loading) root.loading = false
    }
  }

  Timer {
    interval: Math.max(5, root.refreshMinutes) * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    interval: 90 * 1000
    running: root.hasLive
    repeat: true
    onTriggered: {
      if (root.loading || fetchProc.running) return
      root.refresh()
    }
  }

  Component.onCompleted: {
    mkdirProc.running = true
    Qt.callLater(function() {
      cacheFile.reload()
      seenFile.reload()
    })
  }
}
