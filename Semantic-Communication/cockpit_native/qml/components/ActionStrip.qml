import QtQuick 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

PanelFrame {
    id: root

    property var panelData: ({})

    readonly property var panel: DataUtils.objectOrEmpty(panelData)
    readonly property var actions: DataUtils.arrayOrEmpty(panel["actions"])
    readonly property var actionRuntime: shellWindow ? DataUtils.objectOrEmpty(shellWindow.actionRuntime) : ({})
    readonly property var lastAction: shellWindow ? DataUtils.objectOrEmpty(shellWindow.lastActionResult) : ({})
    readonly property var lastActionDetails: DataUtils.arrayOrEmpty(lastAction["detail_lines"])
    readonly property var lastActionLogs: DataUtils.arrayOrEmpty(lastAction["log_lines"])
    readonly property bool busy: !!actionRuntime["busy"]
    readonly property string activeActionId: String(actionRuntime["active_action_id"] || "")
    readonly property var story: shellWindow ? DataUtils.objectOrEmpty(shellWindow.demoStory) : ({})
    readonly property var headline: shellWindow ? DataUtils.objectOrEmpty(shellWindow.performanceHeadline) : ({})
    readonly property bool stackedLayout: width < (shellWindow ? shellWindow.scaled(1380) : 1380)
    readonly property int actionColumns: stackedLayout ? 1 : 2
    readonly property var primaryActions: filteredActions(true)
    readonly property var secondaryActions: filteredActions(false)

    panelColor: shellWindow ? shellWindow.surfaceRaised : "#132434"
    borderTone: shellWindow ? shellWindow.borderStrong : "#5fa0ce"
    accentTone: shellWindow ? shellWindow.accentIce : "#87ddff"

    implicitHeight: contentLayout.implicitHeight + ((shellWindow ? shellWindow.panelPadding : 18) * 2)

    function filteredActions(primary) {
        var preferred = primary
            ? ["current_online_rebuild", "reload_contracts", "probe_live_board"]
            : ["baseline_live_check", "recover_safe_stop", "show_snapshot_path"]
        var ordered = []
        for (var i = 0; i < preferred.length; ++i) {
            var targetId = preferred[i]
            for (var j = 0; j < actions.length; ++j) {
                var candidate = DataUtils.objectOrEmpty(actions[j])
                if (String(candidate["action_id"] || "") === targetId)
                    ordered.push(candidate)
            }
        }
        return ordered
    }

    function toneColor(tone) {
        return shellWindow ? shellWindow.toneColor(tone) : "#87ddff"
    }

    function toneFill(tone) {
        return shellWindow ? shellWindow.toneFill(tone) : "#122838"
    }

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        anchors.margins: shellWindow ? shellWindow.panelPadding : 18
        spacing: shellWindow ? shellWindow.zoneGap : 16

        ShellCard {
            Layout.fillWidth: true
            shellWindow: root.shellWindow
            fillColor: shellWindow ? shellWindow.surfaceGlass : "#1a3144"
            borderColor: shellWindow ? shellWindow.borderStrong : "#5fa0ce"
            accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"
            eyebrow: "ACTION DOCK"
            title: "执行控制台"
            subtitle: String(panel["footer_note"] || "动作通过 repo-backed operator server 承接，返回结果会在右侧执行反馈区展示。")

            GridLayout {
                Layout.fillWidth: true
                columns: stackedLayout ? 1 : 3
                columnSpacing: shellWindow ? shellWindow.zoneGap : 18
                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(2) : 2

                    Text {
                        text: "TRUSTED CURRENT"
                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                    }

                    Text {
                        text: shellWindow ? shellWindow.headlineCurrentValue : "--"
                        color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                        font.pixelSize: shellWindow ? shellWindow.sectionTitleSize + shellWindow.scaled(3) : 36
                        font.weight: Font.DemiBold
                        font.family: shellWindow ? shellWindow.displayFamily : "Sans Serif"
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(2) : 2

                    Text {
                        text: "CURRENT / BASELINE"
                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                    }

                    Text {
                        text: (shellWindow ? shellWindow.headlineBaselineValue : "--") + "  ->  " + (shellWindow ? shellWindow.headlineCurrentValue : "--")
                        color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 18
                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                    }

                    Text {
                        text: "提升 " + (shellWindow ? shellWindow.headlineImprovementValue : "--")
                        color: shellWindow ? shellWindow.accentMint : "#46d7a0"
                        font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                    }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: shellWindow ? shellWindow.actionPageChipModel : []

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

        GridLayout {
            Layout.fillWidth: true
            columns: stackedLayout ? 1 : 2
            columnSpacing: shellWindow ? shellWindow.zoneGap : 18
            rowSpacing: shellWindow ? shellWindow.zoneGap : 18

            ShellCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                shellWindow: root.shellWindow
                accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                eyebrow: "PRIMARY CONTROLS"
                title: "主控动作"
                subtitle: "先点主动作，再看右侧执行反馈。演示时只需要沿着这条主线操作。"

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: root.primaryActions

                        delegate: OperatorActionButton {
                            shellWindow: root.shellWindow
                            Layout.fillWidth: true
                            actionData: modelData
                            compact: false
                        }
                    }
                }
            }

            ShellCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                shellWindow: root.shellWindow
                accentColor: shellWindow ? shellWindow.toneColor(String(lastAction["tone"] || "neutral")) : "#87ddff"
                eyebrow: "EXECUTION FEED"
                title: busy
                    ? ("正在执行 · " + activeActionId)
                    : String(lastAction["label"] || "等待动作回执")
                subtitle: busy
                    ? "请求已发出，等待 operator server / repo-backed live path 返回。"
                    : "这里承接最近一次操作结果、状态摘要和日志尾部。"

                InsetPanel {
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    accentColor: shellWindow ? shellWindow.toneColor(String(lastAction["tone"] || "neutral")) : "#87ddff"
                    prominent: true

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        Text {
                            Layout.fillWidth: true
                            text: String(lastAction["headline"] || "还没有动作回执。先点击左侧动作，结果会落到这里。")
                            color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 18
                            font.weight: Font.DemiBold
                            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            visible: String(lastAction["detail"] || "").length > 0
                            Layout.fillWidth: true
                            text: String(lastAction["detail"] || "")
                            color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                            font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                            font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                            wrapMode: Text.WordWrap
                        }

                        Flow {
                            visible: lastActionDetails.length > 0
                            Layout.fillWidth: true
                            spacing: shellWindow ? shellWindow.compactGap : 8

                            Repeater {
                                model: root.lastActionDetails

                                delegate: ToneChip {
                                    shellWindow: root.shellWindow
                                    label: "detail"
                                    value: String(modelData || "--")
                                    tone: String(lastAction["tone"] || "neutral")
                                }
                            }
                        }

                        ColumnLayout {
                            visible: lastActionLogs.length > 0
                            Layout.fillWidth: true
                            spacing: shellWindow ? shellWindow.scaled(6) : 6

                            Text {
                                text: "LOG TAIL"
                                color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }

                            Repeater {
                                model: root.lastActionLogs

                                delegate: Text {
                                    Layout.fillWidth: true
                                    text: String(modelData || "")
                                    color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }

                InsetPanel {
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                    minimalChrome: true

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: shellWindow ? shellWindow.scaled(4) : 4

                        Text {
                            text: "演示顺序"
                            color: shellWindow ? shellWindow.textMuted : "#5f7384"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                        }

                        Repeater {
                            model: DataUtils.arrayOrEmpty(story["flow"])

                            delegate: Text {
                                Layout.fillWidth: true
                                text: String(Number(index) + 1) + ". " + String(modelData["title"] || "--")
                                color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
        }

        ShellCard {
            Layout.fillWidth: true
            shellWindow: root.shellWindow
            accentColor: shellWindow ? shellWindow.accentBlue : "#78b8e0"
            eyebrow: "SECONDARY CONTROLS"
            title: "次级动作与证据入口"
            subtitle: "补充对照、恢复和只读证据入口，避免把危险动作混进主操作链。"

            GridLayout {
                Layout.fillWidth: true
                columns: root.actionColumns
                columnSpacing: shellWindow ? shellWindow.zoneGap : 18
                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                Repeater {
                    model: root.secondaryActions

                    delegate: OperatorActionButton {
                        shellWindow: root.shellWindow
                        Layout.fillWidth: true
                        actionData: modelData
                        compact: true
                    }
                }
            }
        }
    }
}
