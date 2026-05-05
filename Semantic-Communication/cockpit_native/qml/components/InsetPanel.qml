import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    property var shellWindow: null
    property color accentColor: shellWindow ? shellWindow.accentIce : "#86c7d4"
    property color fillColor: shellWindow ? shellWindow.surfaceQuiet : "#0f161d"
    property int padding: shellWindow ? shellWindow.cardPadding : 14
    property bool prominent: false
    property bool minimalChrome: false
    property bool showAccentRail: true

    default property alias contentData: content.data

    readonly property int accentWidth: shellWindow ? shellWindow.scaled(prominent ? 3 : 2) : (prominent ? 3 : 2)
    readonly property int contentLeftPadding: padding + (showAccentRail ? accentWidth + (shellWindow ? shellWindow.scaled(6) : 6) : 0)

    radius: shellWindow ? shellWindow.edgeRadius + shellWindow.scaled(1) : 13
    color: shellWindow
        ? Qt.rgba(fillColor.r, fillColor.g, fillColor.b, prominent ? 0.82 : (minimalChrome ? 0.58 : 0.72))
        : fillColor
    border.color: shellWindow
        ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, prominent ? 0.42 : (minimalChrome ? 0.14 : 0.22))
        : accentColor
    border.width: 1
    implicitHeight: content.implicitHeight + (padding * 2)

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#18ffffff" }
            GradientStop { position: 0.18; color: "#08ffffff" }
            GradientStop { position: 1.0; color: "#06000000" }
        }
        opacity: root.prominent ? 0.18 : (root.minimalChrome ? 0.06 : 0.12)
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
        anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
        height: shellWindow ? shellWindow.scaled(root.minimalChrome ? 1 : 2) : (root.minimalChrome ? 1 : 2)
        radius: height / 2
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.18; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.minimalChrome ? 0.08 : 0.16) }
            GradientStop { position: 0.5; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.minimalChrome ? 0.48 : 0.9) }
            GradientStop { position: 0.82; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.minimalChrome ? 0.08 : 0.16) }
            GradientStop { position: 1.0; color: "transparent" }
        }
        opacity: root.minimalChrome ? 0.22 : 0.46
    }

    Rectangle {
        visible: root.showAccentRail
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: shellWindow ? shellWindow.scaled(7) : 7
        anchors.topMargin: shellWindow ? shellWindow.scaled(9) : 9
        anchors.bottomMargin: shellWindow ? shellWindow.scaled(9) : 9
        width: root.accentWidth
        radius: width / 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.16; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.minimalChrome ? 0.1 : 0.18) }
            GradientStop { position: 0.48; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.minimalChrome ? 0.68 : 0.94) }
            GradientStop { position: 0.82; color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, root.minimalChrome ? 0.12 : 0.22) }
            GradientStop { position: 1.0; color: "transparent" }
        }
        opacity: root.minimalChrome ? 0.34 : 0.62
    }

    Rectangle {
        width: parent.width * 0.28
        height: parent.height * 0.42
        radius: width / 2
        color: root.accentColor
        opacity: root.prominent ? 0.03 : (root.minimalChrome ? 0.008 : 0.016)
        x: parent.width - (width * 0.7)
        y: -height * 0.2
    }

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.color: Qt.rgba(1, 1, 1, 0.1)
        border.width: 1
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        color: "transparent"
        border.color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.16)
        border.width: 1
        opacity: root.minimalChrome ? 0.2 : 0.34
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.leftMargin: root.contentLeftPadding
        anchors.rightMargin: root.padding
        anchors.topMargin: root.padding
        anchors.bottomMargin: root.padding
        spacing: shellWindow ? shellWindow.compactGap : 8
    }
}
