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
  property int photoMaxHeight: 510

  signal activated(string url)

  width: parent ? parent.width : 0
  implicitHeight: card.height
  height: implicitHeight

  Rectangle {
    id: card
    width: parent.width
    height: inner.height + Style.space(14)
    radius: Style.cornerRadius
    color: "transparent"
    border.width: Style.spacing.hairline
    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.14)

    Column {
      id: inner
      width: parent.width - Style.space(16)
      anchors.left: parent.left
      anchors.leftMargin: Style.space(8)
      anchors.top: parent.top
      anchors.topMargin: Style.space(8)
      spacing: Style.space(6)

      Row {
        width: parent.width
        spacing: Style.space(8)

        Rectangle {
          width: Style.space(32)
          height: Style.space(32)
          radius: width / 2
          clip: true
          color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.08)

          Image {
            anchors.fill: parent
            source: root.modelData.avatar || ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
            visible: source !== ""
            sourceSize.width: 64
            sourceSize.height: 64
          }
        }

        Column {
          width: parent.width - Style.space(40)
          spacing: 0

          Row {
            spacing: Style.space(8)
            width: parent.width

            Text {
              text: root.modelData.authorName || root.modelData.author || ""
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              elide: Text.ElideRight
            }

            Text {
              text: Model.formatAgo(root.modelData.publishedMs, root.nowMs)
              color: root.muted
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
            }
          }

          Text {
            text: root.modelData.handle ? ("@" + root.modelData.handle) : ""
            color: root.muted
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
        }
      }

      Text {
        width: parent.width
        text: root.modelData.title || ""
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.Wrap
        maximumLineCount: 5
        elide: Text.ElideRight
      }

      Image {
        id: photo
        visible: Model.photoUrl(root.modelData) !== ""
        width: parent.width
        height: visible ? Model.photoHeightForWidth(root.modelData, width, root.photoMaxHeight) : 0
        source: Model.photoUrl(root.modelData)
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: true
        sourceSize.width: 598
      }

      Row {
        spacing: Style.space(12)
        visible: (root.modelData.likes || 0) + (root.modelData.retweets || 0) + (root.modelData.replies || 0) > 0

        Text {
          text: Model.formatNumber(root.modelData.replies) + " odp."
          color: root.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }
        Text {
          text: Model.formatNumber(root.modelData.retweets) + " RT"
          color: root.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }
        Text {
          text: Model.formatNumber(root.modelData.likes) + " ♥"
          color: root.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }
      }
    }

    MouseArea {
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: root.activated(root.modelData.url || "")
    }
  }
}
