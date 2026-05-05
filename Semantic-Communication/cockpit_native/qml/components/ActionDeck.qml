import QtQuick 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

PanelFrame {
    id: root

    property var panelData: ({})
    property bool compactMode: false
    property int previewCount: 3

    readonly property var panel: DataUtils.objectOrEmpty(panelData)
    readonly property var actions: DataUtils.arrayOrEmpty(panel["actions"])
    readonly property var demoStory: DataUtils.objectOrEmpty(panel["demo_story"])
    readonly property var runtimeState: shellWindow ? DataUtils.objectOrEmpty(shellWindow.lastActionResult) : ({})
    readonly property bool runtimeBusy: shellWindow ? shellWindow.actionBusy : false
    readonly property int enabledCount: enabledActions()
    readonly property bool twoColumn: width >= (shellWindow ? shellWindow.scaled(1380) : 1380)
    readonly property var featuredAction: resolveFeaturedAction()
    readonly property var secondaryActions: resolveSecondaryActions()
    readonly property var demoFlow: DataUtils.arrayOrEmpty(demoStory["flow"])
    readonly property string runtimeTitle: runtimeBusy
        ? "执行中"
        : (String(runtimeState["headline"] || "等待动作回执"))
    readonly property string runtimeDetail: runtimeSummaryDetail()
    readonly property var dockChipModel: shellWindow ? [
        {
            "label": "LIVE",
            "value": String(enabledCount),
            "tone": enabledCount > 0 ? "online" : "warning"
        },
        {
            "label": "桥接",
            "value": shellWindow.bridgeAvailable ? "在线" : "缺失",
            "tone": shellWindow.bridgeAvailable ? "online" : "warning"
        },
        {
            "label": "渲染",
            "value": shellWindow.softwareRenderEnabled ? "CPU / 软件" : "GPU 优先",
            "tone": shellWindow.softwareRenderEnabled ? "warning" : "online"
        }
    ] : []

    panelColor: shellWindow ? shellWindow.panelColorRaised : "#111b24"
    borderTone: shellWindow ? shellWindow.borderStrong : "#4e6c84"
    accentTone: shellWindow ? shellWindow.accentIce : "#86c7d4"

    implicitHeight: compactMode
        ? compactPreview.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 12) * 2)
        : contentLayout.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 12) * 2)

    function enabledActions() {
        var total = 0
        for (var index = 0; index < actions.length; ++index) {
            var action = DataUtils.objectOrEmpty(actions[index])
            if (!!action["enabled"])
                total += 1
        }
        return total
    }

    function resolveFeaturedAction() {
        for (var index = 0; index < actions.length; ++index) {
            var candidate = DataUtils.objectOrEmpty(actions[index])
            if (String(candidate["action_id"] || "") === "current_online_rebuild")
                return candidate
        }
        return actions.length > 0 ? DataUtils.objectOrEmpty(actions[0]) : ({})
    }

    function resolveSecondaryActions() {
        var featuredId = String(featuredAction["action_id"] || "")
        var resolved = []
        for (var index = 0; index < actions.length; ++index) {
            var candidate = DataUtils.objectOrEmpty(actions[index])
            if (String(candidate["action_id"] || "") === featuredId)
                continue
            resolved.push(candidate)
        }
        return compactMode ? resolved.slice(0, previewCount) : resolved
    }

    function runtimeSummaryDetail() {
        if (String(runtimeState["detail"] || "").length > 0)
            return String(runtimeState["detail"])
        if (String(runtimeState["source_label"] || "").length > 0)
            return String(runtimeState["source_label"])
        return String(panel["footer_note"] || "")
    }

    ColumnLayout {
        id: compactPreview
        visible: root.compactMode
        anchors.fill: parent
        anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
        spacing: shellWindow ? shellWindow.scaled(6) : 6

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.edgeRadius : 12
            color: shellWindow
                ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.62)
                : "#121d26"
            border.color: Qt.rgba(root.accentTone.r, root.accentTone.g, root.accentTone.b, 0.24)
            border.width: 1
            implicitHeight: compactHeaderRow.implicitHeight + ((shellWindow ? shellWindow.scaled(6) : 6) * 2)

            RowLayout {
                id: compactHeaderRow
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.scaled(6) : 6
                spacing: shellWindow ? shellWindow.compactGap : 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        text: "ACTION PREVIEW"
                        color: shellWindow ? shellWindow.accentIce : "#86c7d4"
                        font.pixelSize: shellWindow ? shellWindow.captionSize - 1 : 9
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                    }

                    Text {
                        text: "现场动作预览"
                        color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 16
                        font.weight: Font.DemiBold
                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                    }
                }

                Flow {
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: root.dockChipModel

                        delegate: ToneChip {
                            shellWindow: root.shellWindow
                            label: String(modelData["label"] || "--")
                            value: String(modelData["value"] || "--")
                            tone: String(modelData["tone"] || "neutral")
                        }
                    }
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.compactGap : 8

            OperatorActionButton {
                visible: String(root.featuredAction["action_id"] || "").length > 0
                width: shellWindow ? shellWindow.scaled(280) : 280
                shellWindow: root.shellWindow
                actionData: root.featuredAction
                runtimeState: root.runtimeState
                busy: root.runtimeBusy
                compact: true
                featured: true
            }

            Repeater {
                model: root.secondaryActions

                delegate: OperatorActionButton {
                    width: shellWindow ? shellWindow.scaled(240) : 240
                    shellWindow: root.shellWindow
                    actionData: modelData
                    runtimeState: root.runtimeState
                    busy: root.runtimeBusy
                    compact: true
                }
            }
        }
    }

    ColumnLayout {
        id: contentLayout
        visible: !root.compactMode
        anchors.fill: parent
        anchors.margins: shellWindow ? shellWindow.cardPadding : 12
        spacing: shellWindow ? shellWindow.scaled(8) : 8

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.edgeRadius : 12
            color: shellWindow
                ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.76)
                : "#121d26"
            border.color: Qt.rgba(root.accentTone.r, root.accentTone.g, root.accentTone.b, 0.34)
            border.width: 1
            implicitHeight: headerRow.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                spacing: shellWindow ? shellWindow.compactGap : 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(2) : 2

                    Text {
                        text: compactMode ? "ACTION PREVIEW" : "ACTION CONSOLE"
                        color: shellWindow ? shellWindow.accentIce : "#86c7d4"
                        font.pixelSize: shellWindow ? shellWindow.captionSize - 1 : 9
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(0.8) : 0.8
                    }

                    Text {
                        text: String(panel["title"] || "执行坞站")
                        color: shellWindow ? shellWindow.textStrong : "#f5f8fb"
                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 18
                        font.weight: Font.DemiBold
                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                    }
                }

                Flow {
                    Layout.alignment: Qt.AlignTop
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: root.dockChipModel

                        delegate: ToneChip {
                            shellWindow: root.shellWindow
                            label: String(modelData["label"] || "--")
                            value: String(modelData["value"] || "--")
                            tone: String(modelData["tone"] || "neutral")
                            prominent: index === 0
                        }
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.twoColumn ? 2 : 1
            columnSpacing: shellWindow ? shellWindow.zoneGap : 12
            rowSpacing: shellWindow ? shellWindow.zoneGap : 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: shellWindow ? shellWindow.scaled(8) : 8

                OperatorActionButton {
                    visible: String(root.featuredAction["action_id"] || "").length > 0
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    actionData: root.featuredAction
                    runtimeState: root.runtimeState
                    busy: root.runtimeBusy
                    compact: false
                    featured: true
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: root.twoColumn ? 1 : (width >= (shellWindow ? shellWindow.scaled(980) : 980) ? 2 : 1)
                    columnSpacing: shellWindow ? shellWindow.compactGap : 8
                    rowSpacing: shellWindow ? shellWindow.scaled(6) : 6

                    Repeater {
                        model: root.secondaryActions

                        delegate: OperatorActionButton {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            actionData: modelData
                            runtimeState: root.runtimeState
                            busy: root.runtimeBusy
                            compact: true
                        }
                    }
                }
            }

            ShellCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                shellWindow: root.shellWindow
                accentColor: shellWindow ? shellWindow.accentGold : "#c9a06b"
                eyebrow: "RUNTIME FEED"
                title: root.runtimeTitle
                subtitle: root.runtimeDetail
                padding: shellWindow ? shellWindow.scaled(10) : 10
                contentSpacing: shellWindow ? shellWindow.scaled(6) : 6

                Flow {
                    visible: DataUtils.arrayOrEmpty(runtimeState["detail_lines"]).length > 0
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: DataUtils.arrayOrEmpty(root.runtimeState["detail_lines"])

                        delegate: ToneChip {
                            shellWindow: root.shellWindow
                            label: "detail"
                            value: String(modelData || "--")
                            tone: String(root.runtimeState["tone"] || "neutral")
                        }
                    }
                }

                ColumnLayout {
                    visible: DataUtils.arrayOrEmpty(root.runtimeState["log_lines"]).length > 0
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(4) : 4

                    Text {
                        text: "LOG TAIL"
                        color: shellWindow ? shellWindow.textMuted : "#8397aa"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                    }

                    Repeater {
                        model: DataUtils.arrayOrEmpty(root.runtimeState["log_lines"])

                        delegate: Text {
                            Layout.fillWidth: true
                            text: String(modelData || "")
                            color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Flow {
                    visible: root.demoFlow.length > 0
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: root.demoFlow

                        delegate: ToneChip {
                            shellWindow: root.shellWindow
                            label: "STEP " + String(index + 1)
                            value: String(modelData["title"] || modelData["action_id"] || "--")
                            tone: String(modelData["tone"] || "neutral")
                            prominent: index === 0
                        }
                    }
                }

                Text {
                    visible: !root.runtimeBusy
                        && DataUtils.arrayOrEmpty(root.runtimeState["detail_lines"]).length === 0
                        && DataUtils.arrayOrEmpty(root.runtimeState["log_lines"]).length === 0
                    Layout.fillWidth: true
                    text: "先执行 `Current 在线重建`，再看这里的回执、日志和限制说明。"
                    color: shellWindow ? shellWindow.textSecondary : "#a6b4c1"
                    font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                    font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
