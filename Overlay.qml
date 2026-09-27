import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "Model.js" as Model

Item {
  id: root

  property var shell: null
  property var manifest: null
  property var service: null
  property bool opened: false
  property string filter: "all"

  readonly property color background: Color.menu.background
  readonly property color foreground: Color.menu.text
  readonly property color muted: Qt.darker(foreground, 1.5)
  readonly property color border: Color.menu.border
  readonly property var borderSpec: Border.surfaceSpec("menu", "border", border, Math.max(1, Style.space(2)))
  readonly property color scrim: Color.menu.scrim
  readonly property string fontFamily: Style.font.menuFamily
  readonly property var snapshot: service && service.snapshot ? service.snapshot : Model.emptySnapshot()
  readonly property bool loading: service ? service.loading === true : false
  readonly property var live: Model.liveNow(snapshot)
  readonly property var videos: Model.videoItems(snapshot, filter, true, filter === "all" ? 12 : 24)
  readonly property var tweets: Model.tweetItems(snapshot, 12)
  readonly property var leszekTweets: Model.tweetItemsFor(snapshot, "x-leszek", 12)
  readonly property var kubaTweets: Model.tweetItemsFor(snapshot, "x-kuba", 12)
  readonly property var profiles: Model.xProfiles(snapshot)
  readonly property var links: Model.footerLinks(snapshot)
  readonly property var patronLink: Model.patronLink(snapshot)
  readonly property string patronLine: Model.patronLine(snapshot.patronite)
  readonly property bool showSplit: filter === "all"
  readonly property bool showVideos: filter !== "x"
  readonly property bool showX: filter === "all" || filter === "x"
  readonly property int xColumnWidth: 598
  readonly property var nowMs: clock.date.getTime()
  readonly property var barObj: shell && shell.bar ? shell.bar : null
  readonly property string barPos: barObj && barObj.position ? String(barObj.position) : "top"
  readonly property int barClearance: {
    if (barObj && barObj.barHidden) return Style.gapsOut
    var size = barObj && barObj.barSize ? barObj.barSize : Style.bar.sizeHorizontal
    return size + Style.gapsOut
  }

  function open(payloadJson) {
    root.filter = "all"
    try {
      var payload = JSON.parse(payloadJson || "{}")
      if (payload && payload.filter) root.filter = String(payload.filter)
    } catch (e) {}
    root.opened = true
    if (service && service.refresh) service.refresh()
    Qt.callLater(function() { if (keyCatcher) keyCatcher.forceActiveFocus() })
  }

  function close() {
    root.opened = false
  }

  function dismiss() {
    root.opened = false
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "kjk.tetrycy")
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function setFilter(next) {
    root.filter = next
  }

  function openUrl(url) {
    var target = String(url || "")
    var match = target.match(/^https:\/\/([^\/:?#]+)([\/?#]|$)/)
    if (!match) return
    var host = match[1].toLowerCase()
    var allowed = {
      "www.youtube.com": true,
      "youtube.com": true,
      "m.youtube.com": true,
      "youtu.be": true,
      "x.com": true,
      "twitter.com": true,
      "www.twitter.com": true,
      "mobile.twitter.com": true,
      "www.tetrycy.com.pl": true,
      "tetrycy.com.pl": true,
      "patronite.pl": true,
      "www.patronite.pl": true,
      "discord.gg": true
    }
    if (!allowed[host]) return
    Qt.openUrlExternally(target)
  }

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    margins {
      top: root.barPos === "top" ? root.barClearance : 0
      bottom: root.barPos === "bottom" ? root.barClearance : 0
      left: root.barPos === "left" ? root.barClearance : 0
      right: root.barPos === "right" ? root.barClearance : 0
    }
    color: "transparent"
    WlrLayershell.namespace: "kjk-tetrycy"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore
    mask: Region {
      item: card
    }

    Rectangle {
      anchors.fill: parent
      color: root.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      anchors.fill: parent
      anchors.margins: Style.gapsOut
      radius: Style.cornerRadius
      color: root.background
      borderSpec: root.borderSpec
      padding: Style.spacing.panelPadding

      MouseArea { anchors.fill: parent; onClicked: {} }

      Item {
        id: keyCatcher
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        focus: true
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            root.dismiss()
            event.accepted = true
          } else if (event.key === Qt.Key_R) {
            if (root.service && root.service.refresh) root.service.refresh()
            event.accepted = true
          }
        }

        Column {
          anchors.fill: parent
          spacing: Style.space(12)

          Item {
            id: headerBar
            width: parent.width
            height: Math.max(filterRow.height, headerRight.height) + Style.space(10)

            Row {
              id: filterRow
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(10)

              Repeater {
                model: Model.FILTERS

                Row {
                  required property string modelData
                  required property int index
                  spacing: Style.space(10)

                  Text {
                    visible: index > 0
                    text: "·"
                    color: root.muted
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }

                  Text {
                    text: Model.t(modelData)
                    color: root.filter === modelData ? root.foreground : root.muted
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    font.bold: root.filter === modelData
                    font.letterSpacing: 1
                    MouseArea {
                      anchors.fill: parent
                      anchors.margins: -Style.space(6)
                      hoverEnabled: true
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.setFilter(modelData)
                    }
                  }
                }
              }
            }

            Row {
              id: headerRight
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(16)

              Text {
                visible: !!root.live
                text: Model.t("live")
                color: Color.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                font.letterSpacing: 1
                MouseArea {
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.openUrl(root.live ? root.live.url : "")
                }
              }

              Text {
                text: Model.t("close")
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                font.letterSpacing: 1
                MouseArea {
                  anchors.fill: parent
                  anchors.margins: -Style.space(6)
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.dismiss()
                }
              }
            }
          }

          Row {
            width: parent.width
            height: parent.height - headerBar.height - footerCol.height - Style.space(24)
            spacing: Style.space(18)

            Column {
              id: videoCol
              visible: root.showVideos
              width: !root.showVideos ? 0 : (root.showSplit ? Math.round(parent.width * 0.58) : parent.width)
              height: parent.height
              spacing: Style.space(8)

              PanelSectionHeader {
                id: videoHead
                text: root.filter === "all" ? Model.t("latest") : Model.t(root.filter)
                foreground: root.foreground
                fontFamily: root.fontFamily
                width: parent.width
              }

              TweetList {
                visible: root.showSplit
                width: parent.width
                height: parent.height - videoHead.height - parent.spacing
                model: root.videos
                delegate: VideoCard {
                  width: ListView.view.width
                  compact: true
                  foreground: root.foreground
                  muted: root.muted
                  fontFamily: root.fontFamily
                  nowMs: root.nowMs
                  onActivated: function(url) { root.openUrl(url) }
                }
              }

              VideoGrid {
                visible: !root.showSplit
                width: parent.width
                height: parent.height - videoHead.height - parent.spacing
                columns: 3
                model: root.videos
                delegate: Item {
                  required property var modelData
                  width: GridView.view.cellWidth
                  height: GridView.view.cellHeight

                  VideoCard {
                    anchors.fill: parent
                    anchors.margins: Style.space(7)
                    modelData: parent.modelData
                    foreground: root.foreground
                    muted: root.muted
                    fontFamily: root.fontFamily
                    nowMs: root.nowMs
                    onActivated: function(url) { root.openUrl(url) }
                  }
                }
              }
            }

            Rectangle {
              visible: root.showSplit
              width: Style.spacing.hairline
              height: parent.height
              color: root.foreground
              opacity: 0.12
            }

            Column {
              id: xCol
              visible: root.showX
              width: !root.showX ? 0 : (root.showSplit ? Math.max(Style.space(280), parent.width - videoCol.width - Style.space(20)) : parent.width)
              height: parent.height
              spacing: Style.space(8)

              Row {
                visible: root.showSplit
                width: parent.width
                spacing: Style.space(10)

                PanelSectionHeader {
                  text: Model.t("x")
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                }
              }

              TweetList {
                visible: root.showSplit
                width: parent.width
                height: parent.height - Style.space(36)
                model: root.tweets
                delegate: TweetCard {
                  width: ListView.view.width
                  foreground: root.foreground
                  muted: root.muted
                  fontFamily: root.fontFamily
                  nowMs: root.nowMs
                  onActivated: function(url) { root.openUrl(url) }
                }
              }

              Item {
                visible: root.filter === "x"
                width: parent.width
                height: parent.height

              Row {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, root.xColumnWidth * 2 + Style.space(24))
                height: parent.height
                spacing: Style.space(16)

                Column {
                  width: Math.min(root.xColumnWidth, Math.floor((parent.width - Style.space(16) - Style.spacing.hairline) / 2))
                  height: parent.height
                  spacing: Style.space(8)

                  PanelSectionHeader {
                    id: leszekHead
                    text: Model.t("leszek")
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                  }

                  TweetList {
                    width: parent.width
                    height: parent.height - leszekHead.height - parent.spacing
                    model: root.leszekTweets
                    delegate: TweetCard {
                      width: ListView.view.width
                      foreground: root.foreground
                      muted: root.muted
                      fontFamily: root.fontFamily
                      nowMs: root.nowMs
                      onActivated: function(url) { root.openUrl(url) }
                    }
                  }
                }

                Rectangle {
                  width: Style.spacing.hairline
                  height: parent.height
                  color: root.foreground
                  opacity: 0.12
                }

                Column {
                  width: Math.min(root.xColumnWidth, Math.floor((parent.width - Style.space(16) - Style.spacing.hairline) / 2))
                  height: parent.height
                  spacing: Style.space(8)

                  PanelSectionHeader {
                    id: olkiHead
                    text: Model.t("olki")
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                  }

                  TweetList {
                    width: parent.width
                    height: parent.height - olkiHead.height - parent.spacing
                    model: root.kubaTweets
                    delegate: TweetCard {
                      width: ListView.view.width
                      foreground: root.foreground
                      muted: root.muted
                      fontFamily: root.fontFamily
                      nowMs: root.nowMs
                      onActivated: function(url) { root.openUrl(url) }
                    }
                  }
                }
              }
              }
            }
          }

          Column {
            id: footerCol
            width: parent.width
            spacing: Style.space(6)

            Rectangle {
              width: parent.width
              height: Style.spacing.hairline
              color: root.foreground
              opacity: 0.12
            }

            Row {
              width: parent.width
              spacing: Style.space(10)

              Text {
                textFormat: Text.PlainText
                text: root.patronLink.title
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                MouseArea {
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.openUrl(root.patronLink.url)
                }
              }

              Text {
                textFormat: Text.PlainText
                visible: root.patronLine !== ""
                text: root.patronLine
                color: root.muted
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
              }

              Repeater {
                model: root.links

                Text {
                  textFormat: Text.PlainText
                  required property var modelData
                  text: modelData.title
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.openUrl(modelData.url)
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
