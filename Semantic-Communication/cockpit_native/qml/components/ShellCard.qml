import QtQuick 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    property var shellWindow: null
    property string eyebrow: ""
    property string title: ""
    property string subtitle: ""
    property color fillColor: shellWindow ? shellWindow.surfaceRaised : "#1c1c26"
    property color borderColor: shellWindow ? shellWindow.borderSubtle : "#2c2c3a"
    property color accentColor: shellWindow ? shellWindow.accentBlue : "#5080ff"
    property int padding: shellWindow ? shellWindow.panelPadding : 16
    property int radius: shellWindow ? shellWindow.panelRadius : 16
    property int contentSpacing: shellWindow ? shellWindow.compactGap : 8
    property bool minimalChrome: false
    property int titleSize: 0

    readonly property bool hasHeader: eyebrow.length > 0 || title.length > 0 || subtitle.length > 0

    default property alias contentData: contentLayout.data

    implicitHeight: chrome.implicitHeight + (padding * 2)

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: Qt.rgba(root.fillColor.r, root.fillColor.g, root.fillColor.b, root.minimalChrome ? 0.62 : 0.88)
        border.color: Qt.rgba(root.borderColor.r, root.borderColor.g, root.borderColor.b, root.minimalChrome ? 0.18 : 0.32)
        border.width: 1
    }

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#10ffffff" }
            GradientStop { position: 0.18; color: "#04ffffff" }
            GradientStop { position: 1.0; color: "#05000000" }
        }
        opacity: root.minimalChrome ? 0.12 : 0.24
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
        anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
        height: 1
        radius: height / 2
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.3; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.08) }
            GradientStop { position: 0.5; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.22) }
            GradientStop { position: 0.7; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.06) }
            GradientStop { position: 1.0; color: "transparent" }
        }
        opacity: root.minimalChrome ? 0.28 : 0.5
    }

    ColumnLayout {
        id: chrome
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: root.contentSpacing

        Item {
            visible: root.hasHeader
            Layout.fillWidth: true
            implicitHeight: headerColumn.implicitHeight

            ColumnLayout {
                id: headerColumn
                anchors.fill: parent
                spacing: 4

                Text {
                    visible: root.eyebrow.length > 0
                    text: root.eyebrow
                    color: root.accentColor
                    font.pixelSize: shellWindow ? shellWindow.eyebrowSize : 12
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    font.weight: Font.Medium
                }

                Text {
                    visible: root.title.length > 0
                    Layout.fillWidth: true
                    text: root.title
                    color: shellWindow ? shellWindow.textStrong : "#f0f0f8"
                    font.pixelSize: root.titleSize > 0 ? root.titleSize : (shellWindow ? shellWindow.sectionTitleSize : 22)
                    font.weight: Font.DemiBold
                    font.family: shellWindow ? shellWindow.displayFamily : "Noto Sans CJK SC"
                    wrapMode: Text.WordWrap
                }

                Text {
                    visible: root.subtitle.length > 0 && !root.minimalChrome
                    Layout.fillWidth: true
                    text: root.subtitle
                    color: shellWindow ? shellWindow.textSecondary : "#808098"
                    font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 14
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
        }

        Rectangle {
            visible: root.hasHeader && contentLayout.children.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Qt.rgba(root.borderColor.r, root.borderColor.g, root.borderColor.b, 0.3)
        }

        ColumnLayout {
            id: contentLayout
            Layout.fillWidth: true
            spacing: root.contentSpacing
        }
    }
}
