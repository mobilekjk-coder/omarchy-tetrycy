import QtQuick
import qs.Commons
import "Model.js" as Model

Item {
  id: root

  required property var modelData
  property color foreground
  property color muted
  property string fontFamily
  property var nowMs
  property bool compact: false

  signal activated(string url)

  width: parent ? parent.width : 0
  implicitHeight: compact ? compactRow.height : card.height
  height: implicitHeight

  readonly property string thumbUrl: Model.youtubeThumb(modelData)

  Row {
    id: compactRow
    visible: root.compact
    width: parent.width
    spacing: Style.space(10)

    Image {
      width: Style.space(148)
      height: Math.round(width * 9 / 16)
      source: root.thumbUrl
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: true
      sourceSize.width: 320
      sourceSize.height: 180
    }

    Column {
      width: parent.width - Style.space(158)
      spacing: Style.space(4)
      anchors.verticalCenter: parent.verticalCenter

      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: root.modelData.title || ""
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: Model.sourceBadge(root.modelData) + " · " + Model.formatAgo(root.modelData.publishedMs, root.nowMs)
          + (root.modelData.views ? (" · " + Model.formatViews(root.modelData.views) + " wyśw.") : "")
        color: root.muted
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
      }
    }
  }

  Column {
    id: card
    visible: !root.compact
    width: parent.width
    spacing: Style.space(6)

    Image {
      width: parent.width
      height: Math.round(width * 9 / 16)
      source: root.thumbUrl
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: true
      sourceSize.width: 480
      sourceSize.height: 270
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: root.modelData.title || ""
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      wrapMode: Text.Wrap
      maximumLineCount: 2
      elide: Text.ElideRight
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      text: Model.formatAgo(root.modelData.publishedMs, root.nowMs)
        + (root.modelData.views ? (" · " + Model.formatViews(root.modelData.views) + " wyśw.") : "")
      color: root.muted
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.activated(root.modelData.url || "")
  }
}
