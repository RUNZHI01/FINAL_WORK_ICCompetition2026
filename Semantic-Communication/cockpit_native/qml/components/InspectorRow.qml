import QtQuick 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    property var shellWindow: null
    property string label: ""
    property string value: ""
    property string detail: ""
    property string tone: "neutral"
    property bool prominent: false
    property bool dividerVisible: true

    readonly property color accentColor: shellWindow ? shellWindow.toneColor(tone) : "#86c7d4"

    implicitHeight: content.implicitHeight + (shellWindow ? shellWindow.scaled(10) : 10)

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: shellWindow ? shellWindow.scaled(4) : 4
        spacing: shellWindow ? shellWindow.scaled(2) : 2

        RowLayout {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.scaled(8) : 8

            Text {
                text: root.label
                color: shellWindow ? shellWindow.textMuted : "#8397aa"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                font.letterSpacing: shellWindow ? shellWindow.scaled(0.4) : 0.4
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: shellWindow ? shellWindow.scaled(root.prominent ? 8 : 6) : (root.prominent ? 8 : 6)
                Layout.preferredHeight: width
                radius: width / 2
                color: root.accentColor
                opacity: root.prominent ? 0.82 : 0.62
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.value
            color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
            font.pixelSize: shellWindow
                ? shellWindow.bodySize + (root.prominent ? shellWindow.scaled(2) : shellWindow.scaled(1))
                : (root.prominent ? 16 : 14)
            font.weight: root.prominent ? Font.DemiBold : Font.Medium
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        Text {
            visible: root.detail.length > 0
            Layout.fillWidth: true
            text: root.detail
            color: shellWindow ? shellWindow.textSecondary : "#a6b4c1"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        Rectangle {
            visible: root.dividerVisible
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: shellWindow
                ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.28)
                : "#405463"
        }
    }
}
