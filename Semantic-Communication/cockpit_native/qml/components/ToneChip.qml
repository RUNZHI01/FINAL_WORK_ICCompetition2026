import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property var shellWindow: null
    property string label: ""
    property string value: ""
    property string tone: "neutral"
    property bool prominent: false

    readonly property color accentColor: shellWindow ? shellWindow.toneColor(tone) : "#86c7d4"
    readonly property bool interactive: chipHover.containsMouse

    radius: shellWindow ? shellWindow.edgeRadius : 12
    color: shellWindow
        ? Qt.rgba(shellWindow.surfaceRaised.r, shellWindow.surfaceRaised.g, shellWindow.surfaceRaised.b, prominent ? 0.78 : 0.62)
        : "#17222d"
    border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, prominent ? 0.48 : (interactive ? 0.4 : 0.18))
    border.width: 1
    implicitWidth: content.implicitWidth + ((shellWindow ? shellWindow.scaled(prominent ? 14 : 12) : 12) * 2)
    implicitHeight: content.implicitHeight + ((shellWindow ? shellWindow.scaled(prominent ? 10 : 8) : 8) * 2)
    scale: interactive ? 1.01 : 1.0

    Behavior on scale { NumberAnimation { duration: 120 } }
    Behavior on border.color { ColorAnimation { duration: 120 } }

    MouseArea {
        id: chipHover
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
        anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
        height: 1
        radius: height / 2
        color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, prominent ? 0.62 : 0.34)
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        color: "transparent"
        border.color: Qt.rgba(1, 1, 1, 0.04)
        border.width: 1
    }

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: shellWindow ? shellWindow.scaled(prominent ? 14 : 12) : 12
        anchors.rightMargin: shellWindow ? shellWindow.scaled(prominent ? 14 : 12) : 12
        spacing: shellWindow ? shellWindow.scaled(prominent ? 2 : 1) : 2

        Text {
            visible: root.label.length > 0
            text: root.label
            color: shellWindow ? shellWindow.textMuted : "#8397aa"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
            font.letterSpacing: shellWindow ? shellWindow.scaled(0.6) : 0.6
        }

        Text {
            text: root.value
            color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
            font.pixelSize: shellWindow
                ? shellWindow.bodyEmphasisSize + (prominent ? shellWindow.scaled(1) : 0)
                : 14
            font.weight: Font.DemiBold
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            elide: Text.ElideRight
        }
    }
}
