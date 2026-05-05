import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

Item {
    id: root

    property var shellWindow: null
    property int currentIndex: 0

    readonly property bool compactHeader: shellWindow ? shellWindow.viewportWidth < 1360 : width < 1360
    readonly property bool stackedStatus: shellWindow ? shellWindow.viewportWidth < 1160 : width < 1160
    readonly property var currentPageEntry: shellWindow
        ? DataUtils.objectOrEmpty(shellWindow.navigationModel[currentIndex])
        : ({})
    readonly property string pageSummary: shellWindow ? shellWindow.currentPageSummary : ""
    readonly property var statusModel: shellWindow ? [
        {
            "label": "会话",
            "value": shellWindow.compactMessage(shellWindow.systemSessionValue, compactHeader ? 14 : 18),
            "tone": "neutral"
        },
        {
            "label": "渲染",
            "value": shellWindow.softwareRenderEnabled ? "CPU / 软件" : "图形优先",
            "tone": shellWindow.softwareRenderEnabled ? "warning" : "online"
        }
    ] : []

    signal pageRequested(int index)

    implicitHeight: headerColumn.implicitHeight

    ColumnLayout {
        id: headerColumn
        anchors.fill: parent
        spacing: shellWindow ? shellWindow.scaled(6) : 6

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.edgeRadius + shellWindow.scaled(2) : 16
            color: shellWindow
                ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.76)
                : "#111a22"
            border.color: shellWindow
                ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.42)
                : "#405463"
            border.width: 1
            implicitHeight: topRow.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
            clip: true

            RowLayout {
                id: topRow
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                spacing: shellWindow ? shellWindow.compactGap : 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(1) : 1

                    Text {
                        text: "FEITENG NATIVE COCKPIT"
                        color: shellWindow ? shellWindow.accentIce : "#86c7d4"
                        font.pixelSize: shellWindow ? shellWindow.captionSize - 2 : 8
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(0.9) : 0.9
                    }

                    Text {
                        text: shellWindow ? shellWindow.topTitle : "飞腾原生座舱"
                        color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize + shellWindow.scaled(1) : 20
                        font.weight: Font.DemiBold
                        font.family: shellWindow ? shellWindow.displayFamily : "Sans Serif"
                        elide: Text.ElideRight
                    }

                }

                Flow {
                    Layout.preferredWidth: stackedStatus ? Math.min(parent.width * 0.36, shellWindow ? shellWindow.scaled(240) : 240) : -1
                    Layout.alignment: Qt.AlignTop
                    spacing: shellWindow ? shellWindow.scaled(6) : 6
                    flow: stackedStatus ? Flow.TopToBottom : Flow.LeftToRight

                    Repeater {
                        model: root.statusModel

                        delegate: ToneChip {
                            shellWindow: root.shellWindow
                            label: String(modelData["label"] || "--")
                            value: String(modelData["value"] || "--")
                            tone: String(modelData["tone"] || "neutral")
                            prominent: index === 1
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignTop
                    text: shellWindow
                        ? ("0" + String(root.currentIndex + 1)).slice(-2) + " / " + ("0" + String(shellWindow.navigationModel.length)).slice(-2)
                        : "01 / 05"
                    color: shellWindow ? shellWindow.textMuted : "#8397aa"
                    font.pixelSize: shellWindow ? shellWindow.captionSize - 2 : 8
                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.edgeRadius + shellWindow.scaled(1) : 12
            color: shellWindow
                ? Qt.rgba(shellWindow.surfaceRaised.r, shellWindow.surfaceRaised.g, shellWindow.surfaceRaised.b, 0.54)
                : "#16222d"
            border.color: shellWindow
                ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.36)
                : "#405463"
            border.width: 1
            implicitHeight: navRow.implicitHeight + ((shellWindow ? shellWindow.scaled(4) : 4) * 2)

            RowLayout {
                id: navRow
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.scaled(4) : 4
                spacing: shellWindow ? shellWindow.scaled(6) : 6

                Repeater {
                    model: shellWindow ? shellWindow.navigationModel : []

                    delegate: Rectangle {
                        readonly property bool active: Number(modelData["index"] || 0) === root.currentIndex

                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: active
                            ? Qt.rgba(shellWindow ? shellWindow.accentIce.r : 0.52, shellWindow ? shellWindow.accentIce.g : 0.86, shellWindow ? shellWindow.accentIce.b : 1.0, 0.16)
                            : Qt.rgba(shellWindow ? shellWindow.surfaceQuiet.r : 0.08, shellWindow ? shellWindow.surfaceQuiet.g : 0.11, shellWindow ? shellWindow.surfaceQuiet.b : 0.14, 0.72)
                        border.color: active
                            ? Qt.rgba(shellWindow ? shellWindow.accentIce.r : 0.52, shellWindow ? shellWindow.accentIce.g : 0.86, shellWindow ? shellWindow.accentIce.b : 1.0, 0.78)
                            : Qt.rgba(shellWindow ? shellWindow.borderSubtle.r : 0.3, shellWindow ? shellWindow.borderSubtle.g : 0.4, shellWindow ? shellWindow.borderSubtle.b : 0.5, 0.48)
                        border.width: 1
                        implicitWidth: navContent.implicitWidth + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                        implicitHeight: navContent.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                        Row {
                            id: navContent
                            anchors.centerIn: parent
                            spacing: shellWindow ? shellWindow.scaled(6) : 6

                            Text {
                                text: String(modelData["label"] || "--")
                                color: active
                                    ? (shellWindow ? shellWindow.textStrong : "#f5f8fb")
                                    : (shellWindow ? shellWindow.textPrimary : "#cfe0ec")
                                font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
                                font.weight: Font.Medium
                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                            }

                            Text {
                                text: String(modelData["english"] || "")
                                color: shellWindow ? shellWindow.textMuted : "#8397aa"
                                font.pixelSize: shellWindow ? shellWindow.captionSize - 2 : 8
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.pageRequested(Number(modelData["index"] || 0))
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }
        }
    }
}
