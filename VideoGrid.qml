import QtQuick
import qs.Commons

GridView {
  id: grid

  property int columns: 3

  clip: true
  boundsBehavior: Flickable.StopAtBounds
  flickDeceleration: 10000
  maximumFlickVelocity: 14000
  pixelAligned: true
  cacheBuffer: 600
  reuseItems: true
  displayMarginBeginning: 120
  displayMarginEnd: 120
  cellWidth: Math.max(1, Math.floor(width / Math.max(1, columns)))
  cellHeight: Math.round((cellWidth - Style.space(14)) * 9 / 16) + Style.space(78)

  WheelHandler {
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    onWheel: function(event) {
      var delta = event.pixelDelta.y !== 0 ? event.pixelDelta.y * 1.8 : event.angleDelta.y * 2.4
      var maxY = Math.max(0, grid.contentHeight - grid.height)
      grid.contentY = Math.max(0, Math.min(maxY, grid.contentY - delta))
      event.accepted = true
    }
  }
}
