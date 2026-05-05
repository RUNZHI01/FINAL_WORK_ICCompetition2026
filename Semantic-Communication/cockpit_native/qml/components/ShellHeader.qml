import QtQuick 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

Item {
    id: root

    property var shellWindow: null
    property int currentIndex: 0

    readonly property var currentPageEntry: shellWindow
        ? DataUtils.objectOrEmpty(shellWindow.navigationModel[currentIndex])
        : ({})
    readonly property bool compactHeader: shellWindow ? shellWindow.viewportWidth < 1500 : width < 1500
    readonly property bool stackedHeader: shellWindow ? shellWindow.viewportWidth < 1280 : width < 1280
    readonly property string pageIndicator: shellWindow
        ? ("0" + String(currentIndex + 1)).slice(-2) + " / " + ("0" + String(shellWindow.navigationModel.length)).slice(-2)
        : "01 / 05"
    readonly property string modeLabel: shellWindow
        ? (shellWindow.softwareRenderEnabled ? "软件安全" : "图形优先")
        : "--"
    readonly property string activePageTitle: String(currentPageEntry["label"] || "总览")
    readonly property string activePageEnglish: String(currentPageEntry["english"] || "Landing")
    readonly property string activePageSummary: shellWindow ? shellWindow.currentPageSummary : ""
    readonly property var statusModel: shellWindow ? [
        {
            "label": "会话",
            "value": shellWindow.systemSessionValue,
            "tone": "neutral"
        },
        {
            "label": "心跳",
            "value": shellWindow.heartbeatValue,
            "tone": shellWindow.heartbeatTone
        },
        {
            "label": "数据源",
            "value": shellWindow.compactMessage(shellWindow.activeSourceLabel, compactHeader ? 16 : 26),
            "tone": "online"
        },
        {
            "label": "模式",
            "value": modeLabel,
            "tone": shellWindow.softwareRenderEnabled ? "warning" : "online"
        }
    ] : []

    signal pageRequested(int index)

    implicitHeight: chrome.implicitHeight

    function toneColor(tone) {
        if (shellWindow)
            return shellWindow.toneColor(tone)
        return "#87ddff"
    }

    function toneFill(tone) {
        if (shellWindow)
            return shellWindow.toneFill(tone)
        return "#122838"
    }

    Rectangle {
        id: chrome
        anchors.fill: parent
        implicitHeight: headerColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(16) : 16) * 2)
        radius: shellWindow ? shellWindow.panelRadius + shellWindow.scaled(3) : 28
        color: shellWindow
            ? Qt.rgba(shellWindow.surfaceGlass.r, shellWindow.surfaceGlass.g, shellWindow.surfaceGlass.b, 0.74)
            : "#163042"
        border.color: shellWindow
            ? Qt.rgba(shellWindow.borderStrong.r, shellWindow.borderStrong.g, shellWindow.borderStrong.b, 0.3)
            : "#5fa0ce"
        border.width: 1

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: shellWindow ? Qt.rgba(shellWindow.canopyTop.r, shellWindow.canopyTop.g, shellWindow.canopyTop.b, 0.74) : "#173146" }
                GradientStop { position: 0.35; color: shellWindow ? Qt.rgba(shellWindow.shellInterior.r, shellWindow.shellInterior.g, shellWindow.shellInterior.b, 0.82) : "#132433" }
                GradientStop { position: 1.0; color: shellWindow ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.92) : "#0d1822" }
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: shellWindow ? shellWindow.scaled(22) : 22
            anchors.rightMargin: shellWindow ? shellWindow.scaled(22) : 22
            height: shellWindow ? shellWindow.scaled(2) : 2
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.22; color: shellWindow ? Qt.rgba(shellWindow.accentIce.r, shellWindow.accentIce.g, shellWindow.accentIce.b, 0.14) : "#2287ddff" }
                GradientStop { position: 0.5; color: shellWindow ? Qt.rgba(shellWindow.accentIce.r, shellWindow.accentIce.g, shellWindow.accentIce.b, 0.72) : "#aa87ddff" }
                GradientStop { position: 0.78; color: shellWindow ? Qt.rgba(shellWindow.accentGold.r, shellWindow.accentGold.g, shellWindow.accentGold.b, 0.18) : "#22d9a15a" }
                GradientStop { position: 1.0; color: "transparent" }
            }
            opacity: 0.88
        }

        ColumnLayout {
            id: headerColumn
            anchors.fill: parent
            anchors.margins: shellWindow ? shellWindow.scaled(16) : 16
            spacing: shellWindow ? shellWindow.compactGap : 8

            GridLayout {
                Layout.fillWidth: true
                columns: stackedHeader ? 1 : 3
                columnSpacing: shellWindow ? shellWindow.zoneGap : 18
                rowSpacing: shellWindow ? shellWindow.compactGap : 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(14) : 14

                    Rectangle {
                        Layout.preferredWidth: shellWindow ? shellWindow.scaled(60) : 60
                        Layout.preferredHeight: shellWindow ? shellWindow.scaled(60) : 60
                        radius: shellWindow ? shellWindow.scaled(18) : 18
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: shellWindow ? shellWindow.accentGold : "#d9a15a" }
                            GradientStop { position: 1.0; color: shellWindow ? shellWindow.accentIce : "#87ddff" }
                        }

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 1
                            radius: parent.radius - 1
                            color: shellWindow ? shellWindow.shellExterior : "#0b1620"
                        }

                        Text {
                            anchors.centerIn: parent
                            text: "FP"
                            color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 20
                            font.weight: Font.DemiBold
                            font.family: shellWindow ? shellWindow.displayFamily : "Sans Serif"
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: shellWindow ? shellWindow.scaled(2) : 2

                        Text {
                            Layout.fillWidth: true
                            text: "FEITENG NATIVE COCKPIT"
                            color: shellWindow ? shellWindow.accentIce : "#87ddff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 13
                            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            font.letterSpacing: shellWindow ? shellWindow.scaled(1.1) : 1.1
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: shellWindow ? shellWindow.topTitle : "飞腾原生座舱"
                            color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                            font.pixelSize: shellWindow ? shellWindow.headerTitleSize : 42
                            font.weight: Font.DemiBold
                            font.family: shellWindow ? shellWindow.displayFamily : "Sans Serif"
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            text: activePageTitle + " / " + activePageEnglish + " · " + activePageSummary
                            color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                            font.pixelSize: shellWindow ? shellWindow.bodySize : 16
                            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                            maximumLineCount: stackedHeader ? 2 : 1
                            elide: Text.ElideRight
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: shellWindow ? shellWindow.cardRadius : 18
                    color: shellWindow
                        ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.82)
                        : "#0d1822"
                    border.color: shellWindow
                        ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.65)
                        : "#274257"
                    border.width: 1
                    implicitHeight: summaryRow.implicitHeight + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)

                    RowLayout {
                        id: summaryRow
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.scaled(12) : 12
                        spacing: shellWindow ? shellWindow.zoneGap : 18

                        ColumnLayout {
                            spacing: 2

                            Text {
                                text: "TRUSTED PAYLOAD"
                                color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }

                            Text {
                                text: shellWindow ? shellWindow.headlineCurrentValue : "--"
                                color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                font.pixelSize: shellWindow ? shellWindow.sectionTitleSize + shellWindow.scaled(2) : 34
                                font.weight: Font.DemiBold
                                font.family: shellWindow ? shellWindow.displayFamily : "Sans Serif"
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                Layout.fillWidth: true
                                text: shellWindow ? shellWindow.performanceHeadline["summary"] || shellWindow.currentPageSummary : activePageSummary
                                color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                font.pixelSize: shellWindow ? shellWindow.bodySize : 15
                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                wrapMode: Text.WordWrap
                                maximumLineCount: compactHeader ? 2 : 1
                                elide: Text.ElideRight
                            }

                            RowLayout {
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Text {
                                    text: "baseline " + (shellWindow ? shellWindow.headlineBaselineValue : "--")
                                    color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                }

                                Text {
                                    text: "提升 " + (shellWindow ? shellWindow.headlineImprovementValue : "--")
                                    color: shellWindow ? shellWindow.accentMint : "#46d7a0"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                }

                                Text {
                                    text: "speedup " + (shellWindow ? shellWindow.headlineSpeedupValue : "--")
                                    color: shellWindow ? shellWindow.accentGold : "#d9a15a"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: shellWindow ? shellWindow.cardRadius : 18
                    color: shellWindow
                        ? Qt.rgba(shellWindow.surfaceRaised.r, shellWindow.surfaceRaised.g, shellWindow.surfaceRaised.b, 0.78)
                        : "#132434"
                    border.color: shellWindow
                        ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.65)
                        : "#274257"
                    border.width: 1
                    implicitHeight: contextColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)

                    ColumnLayout {
                        id: contextColumn
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.scaled(12) : 12
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        RowLayout {
                            Layout.fillWidth: true

                            Text {
                                Layout.fillWidth: true
                                text: "GLOBAL STATUS"
                                color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }

                            Text {
                                text: pageIndicator
                                color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }
                        }

                        Flow {
                            Layout.fillWidth: true
                            spacing: shellWindow ? shellWindow.compactGap : 8

                            Repeater {
                                model: root.statusModel

                                delegate: Rectangle {
                                    readonly property var chip: modelData
                                    radius: shellWindow ? shellWindow.edgeRadius : 14
                                    color: root.toneFill(chip["tone"])
                                    border.color: Qt.rgba(root.toneColor(chip["tone"]).r, root.toneColor(chip["tone"]).g, root.toneColor(chip["tone"]).b, 0.52)
                                    border.width: 1
                                    implicitWidth: chipRow.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                                    implicitHeight: chipRow.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                                    RowLayout {
                                        id: chipRow
                                        anchors.centerIn: parent
                                        spacing: shellWindow ? shellWindow.scaled(8) : 8

                                        Rectangle {
                                            Layout.preferredWidth: shellWindow ? shellWindow.scaled(7) : 7
                                            Layout.preferredHeight: width
                                            radius: width / 2
                                            color: root.toneColor(chip["tone"])
                                        }

                                        ColumnLayout {
                                            spacing: 1

                                            Text {
                                                text: chip["label"]
                                                color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                            }

                                            Text {
                                                text: chip["value"]
                                                color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                                font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 15
                                                font.weight: Font.DemiBold
                                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: shellWindow
                    ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.65)
                    : "#274257"
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: shellWindow ? shellWindow.compactGap : 8

                Repeater {
                    model: shellWindow ? shellWindow.navigationModel : []

                    delegate: Rectangle {
                        readonly property bool active: Number(modelData["index"] || 0) === root.currentIndex
                        readonly property color accentColor: active
                            ? (shellWindow ? shellWindow.accentIce : "#87ddff")
                            : (shellWindow ? shellWindow.borderSubtle : "#274257")

                        Layout.fillWidth: true
                        radius: shellWindow ? shellWindow.edgeRadius + shellWindow.scaled(1) : 16
                        color: active
                            ? (shellWindow ? Qt.rgba(shellWindow.surfaceRaised.r, shellWindow.surfaceRaised.g, shellWindow.surfaceRaised.b, 0.96) : "#132434")
                            : (shellWindow ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.78) : "#0d1822")
                        border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, active ? 0.76 : 0.38)
                        border.width: 1
                        implicitHeight: tabContent.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)

                        Rectangle {
                            visible: active
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: shellWindow ? shellWindow.scaled(12) : 12
                            anchors.rightMargin: shellWindow ? shellWindow.scaled(12) : 12
                            height: shellWindow ? shellWindow.scaled(2) : 2
                            radius: height / 2
                            color: accentColor
                            opacity: 0.9
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.pageRequested(Number(modelData["index"] || 0))
                        }

                        RowLayout {
                            id: tabContent
                            anchors.fill: parent
                            anchors.margins: shellWindow ? shellWindow.scaled(12) : 12
                            spacing: shellWindow ? shellWindow.scaled(10) : 10

                            Text {
                                text: ("0" + String(Number(modelData["index"] || 0) + 1)).slice(-2)
                                color: active ? accentColor : (shellWindow ? shellWindow.textMuted : "#5f7384")
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1

                                Text {
                                    text: String(modelData["label"] || "--")
                                    color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 16
                                    font.weight: active ? Font.DemiBold : Font.Medium
                                    font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                }

                                Text {
                                    text: String(modelData["summary"] || "")
                                    color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                    font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                    maximumLineCount: compactHeader ? 2 : 1
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
