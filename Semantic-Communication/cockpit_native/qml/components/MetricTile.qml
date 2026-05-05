import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property var shellWindow: null
    property string label: ""
    property string value: ""
    property string detail: ""
    property string tone: "neutral"
    property bool prominent: false
    property int entranceDelay: 0

    readonly property color accentColor: shellWindow ? shellWindow.toneColor(tone) : "#86c7d4"
    readonly property bool hovered: hoverArea.containsMouse

    opacity: 0
    Component.onCompleted: entranceAnim.start()

    SequentialAnimation {
        id: entranceAnim
        PauseAnimation { duration: root.entranceDelay }
        NumberAnimation { target: root; property: "opacity"; from: 0; to: 1; duration: 240; easing.type: Easing.OutCubic }
    }

    radius: shellWindow ? shellWindow.cardRadius : 16
    color: shellWindow
        ? Qt.rgba(shellWindow.surfaceRaised.r, shellWindow.surfaceRaised.g, shellWindow.surfaceRaised.b, prominent ? 0.8 : 0.64)
        : "#16222d"
    border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, prominent ? 0.5 : (hovered ? 0.38 : 0.16))
    border.width: 1
    implicitHeight: body.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 14) * 2)
    scale: hovered ? 1.01 : 1.0

    Behavior on scale { NumberAnimation { duration: 140 } }
    Behavior on border.color { ColorAnimation { duration: 140 } }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
        anchors.topMargin: shellWindow ? shellWindow.scaled(12) : 12
        anchors.bottomMargin: shellWindow ? shellWindow.scaled(12) : 12
        width: shellWindow ? shellWindow.scaled(prominent ? 4 : 3) : (prominent ? 4 : 3)
        radius: width / 2
        color: accentColor
        opacity: prominent ? 0.82 : 0.54
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        color: "transparent"
        border.color: Qt.rgba(1, 1, 1, 0.035)
        border.width: 1
    }

    ColumnLayout {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: shellWindow ? shellWindow.cardPadding + shellWindow.scaled(8) : 18
        anchors.rightMargin: shellWindow ? shellWindow.cardPadding : 14
        anchors.topMargin: shellWindow ? shellWindow.cardPadding : 14
        anchors.bottomMargin: shellWindow ? shellWindow.cardPadding : 14
        spacing: shellWindow ? shellWindow.scaled(4) : 4

        Text {
            text: root.label
            color: shellWindow ? shellWindow.textMuted : "#8397aa"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
            font.letterSpacing: shellWindow ? shellWindow.scaled(0.5) : 0.5
        }

        Text {
            Layout.fillWidth: true
            text: root.value
            color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
            font.pixelSize: shellWindow
                ? shellWindow.bodyEmphasisSize + (root.prominent ? shellWindow.scaled(3) : shellWindow.scaled(1))
                : (root.prominent ? 20 : 16)
            font.weight: Font.DemiBold
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            wrapMode: Text.WordWrap
            maximumLineCount: root.prominent ? 3 : 2
            elide: Text.ElideRight
        }

        Text {
            visible: root.detail.length > 0
            Layout.fillWidth: true
            text: root.detail
            color: shellWindow ? shellWindow.textSecondary : "#a6b4c1"
            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }
    }
}
