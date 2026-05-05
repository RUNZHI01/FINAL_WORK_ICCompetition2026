import QtQuick 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

Rectangle {
    id: root

    property var shellWindow: null
    property var actionData: ({})
    property var runtimeState: ({})
    property bool compact: false
    property bool featured: false
    property bool busy: false

    readonly property var action: DataUtils.objectOrEmpty(actionData)
    readonly property var runtime: DataUtils.objectOrEmpty(runtimeState)
    readonly property bool interactiveAction: !!action["interactive"]
    readonly property bool readyAction: interactiveAction && !!action["enabled"]
    readonly property string toneValue: String(action["runtime_tone"] || action["tone"] || "neutral")
    readonly property color accentColor: shellWindow ? shellWindow.toneColor(toneValue) : "#86c7d4"
    readonly property bool hovered: hoverArea.containsMouse
    readonly property bool pressed: hoverArea.pressed
    readonly property string actionId: String(action["action_id"] || "")
    readonly property bool selected: String(runtime["action_id"] || "") === actionId
    readonly property bool actionBusy: root.busy && selected
    readonly property string runtimeStatus: String(runtime["status"] || "")
    readonly property string statusLabel: actionBusy
        ? "执行中"
        : (selected && runtimeStatus.length > 0
            ? runtimeStatus
            : (readyAction ? "LIVE 就绪" : (interactiveAction ? "受限调用" : "只读镜像")))
    readonly property string detailLabel: String(
        (selected && runtime["message"]) || action["runtime_detail"] || action["limitation"] || action["note"] || ""
    )
    readonly property string ctaLabel: interactiveAction
        ? String(action["cta_label"] || "执行动作")
        : "只读合同"
    readonly property bool denseCard: compact || !featured
    readonly property color fillColor: featured
        ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, hovered ? 0.18 : 0.13)
        : (shellWindow
            ? Qt.rgba(shellWindow.surfaceRaised.r, shellWindow.surfaceRaised.g, shellWindow.surfaceRaised.b, hovered ? 0.84 : 0.72)
            : "#16222d")

    radius: shellWindow ? shellWindow.cardRadius : 16
    color: fillColor
    border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, selected ? 0.88 : (hovered ? 0.58 : 0.28))
    border.width: 1
    implicitHeight: contentColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(denseCard ? 10 : 14) : (denseCard ? 10 : 14)) * 2)
    scale: interactiveAction && hovered ? 1.01 : 1.0

    Behavior on scale { NumberAnimation { duration: 120 } }
    Behavior on border.color { ColorAnimation { duration: 120 } }
    Behavior on color { ColorAnimation { duration: 120 } }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
        anchors.topMargin: shellWindow ? shellWindow.scaled(12) : 12
        anchors.bottomMargin: shellWindow ? shellWindow.scaled(12) : 12
        width: shellWindow ? shellWindow.scaled(featured ? 4 : 3) : (featured ? 4 : 3)
        radius: width / 2
        color: accentColor
        opacity: selected ? 0.96 : 0.72
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        color: "transparent"
        border.color: Qt.rgba(1, 1, 1, 0.05)
        border.width: 1
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        enabled: interactiveAction && !root.busy
        hoverEnabled: interactiveAction
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: {
            if (shellWindow && shellWindow.invokeOperatorAction)
                shellWindow.invokeOperatorAction(action)
        }
    }

    ColumnLayout {
        id: contentColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: shellWindow ? shellWindow.cardPadding + shellWindow.scaled(8) : 18
        anchors.rightMargin: shellWindow ? shellWindow.cardPadding : 14
        anchors.topMargin: shellWindow ? shellWindow.scaled(denseCard ? 10 : 14) : (denseCard ? 10 : 14)
        anchors.bottomMargin: shellWindow ? shellWindow.scaled(denseCard ? 10 : 14) : (denseCard ? 10 : 14)
        spacing: shellWindow ? shellWindow.scaled(denseCard ? 4 : 6) : (denseCard ? 4 : 6)

        RowLayout {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.compactGap : 8

            Rectangle {
                radius: shellWindow ? shellWindow.edgeRadius : 10
                color: shellWindow ? shellWindow.toneFill(toneValue) : "#102033"
                border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.56)
                border.width: 1
                implicitWidth: actionIdLabel.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                implicitHeight: actionIdLabel.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                Text {
                    id: actionIdLabel
                    anchors.centerIn: parent
                    text: actionId
                    color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                radius: height / 2
                color: actionBusy
                    ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.18)
                    : (readyAction
                        ? Qt.rgba(0.27, 0.8, 0.58, 0.16)
                        : Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.1))
                border.color: actionBusy
                    ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.8)
                    : (readyAction ? "#45d79b" : Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.42))
                border.width: 1
                implicitWidth: statusText.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                implicitHeight: statusText.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                Text {
                    id: statusText
                    anchors.centerIn: parent
                    text: statusLabel
                    color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: String(action["label"] || "--")
            color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
            font.pixelSize: shellWindow
                ? shellWindow.bodyEmphasisSize + (featured ? shellWindow.scaled(1) : shellWindow.scaled(-1))
                : (featured ? 18 : 15)
            font.weight: Font.DemiBold
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            wrapMode: Text.WordWrap
            maximumLineCount: denseCard ? 2 : 3
            elide: Text.ElideRight
        }

        Text {
            visible: detailLabel.length > 0
            Layout.fillWidth: true
            text: detailLabel
            color: shellWindow ? shellWindow.textSecondary : "#a6b4c1"
            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
            wrapMode: Text.WordWrap
            maximumLineCount: denseCard ? 2 : 3
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            text: ctaLabel
            color: accentColor
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
            font.letterSpacing: shellWindow ? shellWindow.scaled(0.5) : 0.5
            elide: Text.ElideRight
        }
    }
}
