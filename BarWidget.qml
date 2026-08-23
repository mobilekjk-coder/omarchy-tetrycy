import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

BarWidget {
  id: root
  moduleName: "kjk.tetrycy"

  property var snapshot: Model.emptySnapshot()

  readonly property var service: bar && bar.shell && bar.shell.serviceFor ? bar.shell.serviceFor("kjk.tetrycy") : null
  readonly property var nowMs: clock.date.getTime()
  readonly property var liveSnapshot: service && service.snapshot ? service.snapshot : snapshot
  readonly property string displayText: "TETRYCY"
  readonly property var verticalLines: displayText.split("\n")
  readonly property bool hasLive: !!Model.liveNow(liveSnapshot)

  function applySettings() {
    if (!service) return
    service.refreshMinutes = Math.max(5, parseInt(setting("refreshMinutes", 10), 10) || 10)
    service.showShorts = setting("showShorts", true) !== false
    service.notifyNew = setting("notifyNew", true) !== false
  }

  function summonOverlay() {
    if (!root.bar) return
    root.bar.run("omarchy-shell shell toggle kjk.tetrycy")
  }

  function refresh() {
    if (service && service.refresh) service.refresh()
  }

  readonly property bool opened: {
    var sh = bar && bar.shell
    if (sh && typeof sh.isPluginOpen === "function") return sh.isPluginOpen("kjk.tetrycy") === true
    return false
  }

  function open() { summonOverlay() }
  function close() {
    if (root.bar) root.bar.run("omarchy-shell shell hide kjk.tetrycy")
  }
  function togglePanel() { summonOverlay() }

  readonly property bool popoutSwitchClosing: false
  function closeForPopoutSwitch() {}

  readonly property real openPanelIndicatorWidth: button.labelWidth
  readonly property real openPanelIndicatorHeight: Math.max(Style.space(10), Math.round(Style.bar.iconSlot * 0.55))

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: applySettings()
  onSettingsChanged: applySettings()

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
  }

  FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/kjk.tetrycy/cache.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var cached = Model.parseCache(text(), Date.now())
      if (cached.ok) root.snapshot = cached
    }
  }

  Timer {
    interval: 1000
    running: service === null
    repeat: true
    onTriggered: root.applySettings()
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.vertical ? "" : root.displayText
    labelVisible: !root.vertical
    hasVisualContent: root.vertical ? root.verticalLines.length > 0 : text !== ""
    fixedHeight: root.vertical ? root.verticalLines.length * Style.bar.iconSlot : -1
    horizontalMargin: 8.75
    verticalPadding: 8.75
    tooltipText: ""
    active: root.hasLive

    onPressed: function(b) {
      if (!root.bar) return
      if (b === Qt.RightButton) {
        if (service && service.notifyLatest) service.notifyLatest()
      } else if (b === Qt.MiddleButton) {
        root.refresh()
      } else {
        root.summonOverlay()
      }
    }

    Column {
      visible: root.vertical
      anchors.fill: parent

      Repeater {
        model: root.verticalLines

        OpticalGlyph {
          required property string modelData
          width: button.width
          height: Style.bar.iconSlot
          text: modelData
          fontFamily: button.fontFamily
          fontSize: modelData.length > 3 ? button.fontSize * 0.9 : button.fontSize
          color: button.foreground
        }
      }
    }
  }
}
