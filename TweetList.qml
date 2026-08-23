import QtQuick
import qs.Commons

ListView {
  id: list

  clip: true
  spacing: Style.space(10)
  boundsBehavior: Flickable.StopAtBounds
  flickDeceleration: 10000
  maximumFlickVelocity: 14000
  pixelAligned: true
  cacheBuffer: 480
  reuseItems: true
  displayMarginBeginning: 120
  displayMarginEnd: 120

  WheelHandler {
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    onWheel: function(event) {
      var delta = event.pixelDelta.y !== 0 ? event.pixelDelta.y * 1.8 : event.angleDelta.y * 2.4
      var maxY = Math.max(0, list.contentHeight - list.height)
      list.contentY = Math.max(0, Math.min(maxY, list.contentY - delta))
      event.accepted = true
    }
  }
}
