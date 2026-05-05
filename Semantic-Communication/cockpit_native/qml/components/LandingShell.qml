import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

Item {
    id: root

    property var shellWindow: null

    readonly property var statusRows: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.statusRows) : []
    readonly property var centerPanel: shellWindow ? DataUtils.objectOrEmpty(shellWindow.centerPanelData) : ({})
    readonly property var sampleData: DataUtils.objectOrEmpty(centerPanel["sample"])
    readonly property var feedContract: shellWindow ? DataUtils.objectOrEmpty(shellWindow.centerFeedContract) : ({})
    readonly property var actionList: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.bottomActions) : []
    readonly property var trackData: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.trackData) : []
    readonly property var currentPoint: shellWindow ? DataUtils.objectOrEmpty(shellWindow.currentPosition) : ({})
    readonly property real headingDeg: shellWindow ? Number(shellWindow.kinematics["heading_deg"] || 0) : 0
    readonly property var liveAnchor: shellWindow ? DataUtils.objectOrEmpty(shellWindow.liveAnchor) : ({})
    readonly property var scenarioList: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.rightScenarios) : []
    readonly property var recommendedScenario: shellWindow ? DataUtils.objectOrEmpty(shellWindow.recommendedScenario) : ({})
    readonly property var recommendedComparison: shellWindow ? DataUtils.objectOrEmpty(shellWindow.recommendedComparison) : ({})
    readonly property var stageTimingList: DataUtils.arrayOrEmpty(recommendedScenario["stage_timings"])
    readonly property var evidenceList: DataUtils.arrayOrEmpty(recommendedScenario["evidence"])
    readonly property bool singleColumn: shellWindow ? shellWindow.viewportWidth < 1320 : width < 1320
    readonly property bool splitLanding: shellWindow ? shellWindow.viewportWidth >= 1780 : width >= 1780
    readonly property bool compactPage: shellWindow ? shellWindow.viewportWidth < 1600 : width < 1600
    readonly property int sideRailWidth: shellWindow ? shellWindow.scaled(compactPage ? 332 : 382) : 382
    readonly property int stagePreferredHeight: shellWindow ? shellWindow.scaled(singleColumn ? 430 : 620) : 620
    readonly property int flightStageHeight: shellWindow ? shellWindow.scaled(singleColumn ? 540 : 920) : 920
    readonly property var primaryActions: selectActions(["current_online_rebuild", "reload_contracts", "probe_live_board"])
    readonly property var secondaryActions: selectActions(["baseline_live_check", "recover_safe_stop", "show_snapshot_path"])
    readonly property var systemOverviewModel: shellWindow ? [
        {
            "label": "会话",
            "value": shellWindow.systemSessionValue,
            "detail": shellWindow.eventTimeValue,
            "tone": "neutral"
        },
        {
            "label": "心跳",
            "value": shellWindow.heartbeatValue,
            "detail": shellWindow.snapshotReasonValue,
            "tone": shellWindow.heartbeatTone
        },
        {
            "label": "最近事件",
            "value": compact(shellWindow.recentEventValue, compactPage ? 18 : 24),
            "detail": shellWindow.snapshotRelativePath,
            "tone": shellWindow.recentEventTone
        },
        {
            "label": "链路档位",
            "value": shellWindow.linkProfileValue,
            "detail": shellWindow.activeSourceLabel,
            "tone": "neutral"
        }
    ] : []
    readonly property var weakOverviewModel: shellWindow ? [
        {
            "label": "推荐档",
            "value": shellWindow.recommendedScenarioId,
            "detail": compact(String(recommendedScenario["summary"] || recommendedScenario["label"] || "延续当前弱网推荐。"), compactPage ? 26 : 44),
            "tone": "warning"
        },
        {
            "label": "在线锚点",
            "value": String(liveAnchor["valid_instance"] || "--"),
            "detail": compact(String(liveAnchor["board_status"] || liveAnchor["probe_summary"] || "等待在线锚点"), compactPage ? 26 : 40),
            "tone": shellWindow.liveAnchorTone
        },
        {
            "label": "吞吐",
            "value": shellWindow.formattedMetric(recommendedComparison["pipeline_images_per_sec"], 3, "img/s"),
            "detail": "pipeline current",
            "tone": "online"
        },
        {
            "label": "提升",
            "value": shellWindow.formattedMetric(recommendedComparison["throughput_uplift_pct"], 3, "%"),
            "detail": "throughput uplift",
            "tone": "warning"
        }
    ] : []
    readonly property var flightContractModel: [
        {
            "label": "来源状态",
            "value": String(centerPanel["source_status"] || "--"),
            "detail": String(feedContract["active_source_kind"] || "--"),
            "tone": "online"
        },
        {
            "label": "数据源",
            "value": compact(feedContract["active_source_label"] || centerPanel["source_label"] || "--", compactPage ? 18 : 26),
            "detail": String(centerPanel["source_api_path"] || "--"),
            "tone": "neutral"
        },
        {
            "label": "采样时间",
            "value": String(sampleData["captured_at"] || "--"),
            "detail": String(sampleData["source"] || "contract sample"),
            "tone": "neutral"
        },
        {
            "label": "回退语义",
            "value": compact(centerPanel["fallback_note"] || "--", compactPage ? 22 : 34),
            "detail": compact(centerPanel["ownership_note"] || "--", compactPage ? 22 : 34),
            "tone": "warning"
        }
    ]
    readonly property var actionEchoDetails: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.lastActionResult["detail_lines"]) : []
    readonly property var actionEchoLogs: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.lastActionResult["log_lines"]) : []

    function compact(text, limit) {
        if (shellWindow)
            return shellWindow.compactMessage(text, limit)
        return String(text || "")
    }

    function selectActions(order) {
        var resolved = []
        for (var i = 0; i < order.length; ++i) {
            var actionId = String(order[i] || "")
            for (var j = 0; j < actionList.length; ++j) {
                var candidate = DataUtils.objectOrEmpty(actionList[j])
                if (String(candidate["action_id"] || "") === actionId)
                    resolved.push(candidate)
            }
        }
        return resolved
    }

    function scenarioComparison(scenario) {
        return DataUtils.objectOrEmpty(DataUtils.objectOrEmpty(scenario)["comparison"])
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            width: parent.width * 0.42
            height: parent.height * 0.54
            radius: width / 2
            x: parent.width * 0.62
            y: -height * 0.22
            color: shellWindow ? shellWindow.haloCool : "#1f5f95"
            opacity: 0.08
        }

        Rectangle {
            width: parent.width * 0.35
            height: parent.height * 0.44
            radius: width / 2
            x: -width * 0.18
            y: parent.height * 0.54
            color: shellWindow ? shellWindow.haloWarm : "#4d5f84"
            opacity: 0.06
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: shellWindow ? shellWindow.shellPadding : 20
        spacing: shellWindow ? shellWindow.zoneGap : 16

        ShellHeader {
            Layout.fillWidth: true
            shellWindow: root.shellWindow
            currentIndex: shellWindow ? shellWindow.currentPage : 0
            onPageRequested: function(index) {
                if (shellWindow)
                    shellWindow.currentPage = index
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: shellWindow ? shellWindow.currentPage : 0

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: shellWindow ? shellWindow.zoneGap : 16

                    ShellCard {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        fillColor: shellWindow ? shellWindow.surfaceGlass : "#1a3144"
                        borderColor: shellWindow ? shellWindow.borderStrong : "#5fa0ce"
                        accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"
                        eyebrow: "GLOBAL COMMAND STAGE"
                        title: shellWindow ? shellWindow.missionCallSignValue + " · " + shellWindow.aircraftIdValue : "M9-DEMO · FT-AIR-01"
                        subtitle: shellWindow ? shellWindow.performanceHeadline["summary"] || shellWindow.currentPageSummary : ""

                        GridLayout {
                            Layout.fillWidth: true
                            columns: singleColumn ? 1 : 3
                            columnSpacing: shellWindow ? shellWindow.zoneGap : 16
                            rowSpacing: shellWindow ? shellWindow.compactGap : 8

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: shellWindow ? shellWindow.scaled(2) : 2

                                Text {
                                    text: "CURRENT"
                                    color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                    font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                }

                                Text {
                                    text: shellWindow ? shellWindow.headlineCurrentValue : "--"
                                    color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                    font.pixelSize: shellWindow ? shellWindow.sectionTitleSize + shellWindow.scaled(4) : 38
                                    font.weight: Font.DemiBold
                                    font.family: shellWindow ? shellWindow.displayFamily : "Sans Serif"
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: shellWindow ? shellWindow.scaled(2) : 2

                                Text {
                                    text: "BASELINE / IMPROVEMENT"
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
                                    text: "提升 " + (shellWindow ? shellWindow.headlineImprovementValue : "--") + " · speedup " + (shellWindow ? shellWindow.headlineSpeedupValue : "--")
                                    color: shellWindow ? shellWindow.accentMint : "#46d7a0"
                                    font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                                    font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                }
                            }

                            Flow {
                                Layout.fillWidth: true
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: shellWindow ? shellWindow.topStatusModel : []

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
                        Layout.fillHeight: true
                        columns: singleColumn ? 1 : 3
                        columnSpacing: shellWindow ? shellWindow.zoneGap : 16
                        rowSpacing: shellWindow ? shellWindow.zoneGap : 16

                        ShellCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: sideRailWidth
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentBlue : "#78b8e0"
                            eyebrow: "SYSTEM RAIL"
                            title: "系统健康"
                            subtitle: shellWindow ? shellWindow.truthNoteValue : ""

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 1
                                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: root.systemOverviewModel

                                    delegate: MetricTile {
                                        shellWindow: root.shellWindow
                                        Layout.fillWidth: true
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        detail: String(modelData["detail"] || "")
                                        tone: String(modelData["tone"] || "neutral")
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
                                        text: "快照路径"
                                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: shellWindow ? shellWindow.snapshotRelativePath : "--"
                                        color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        ShellCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: shellWindow ? shellWindow.scaled(splitLanding ? 1120 : 860) : 860
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"
                            eyebrow: "MAP STAGE"
                            title: shellWindow ? shellWindow.landingSummaryTitle : "全球任务态势主墙"
                            subtitle: shellWindow ? shellWindow.landingSummaryText : ""

                            Flow {
                                Layout.fillWidth: true
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: shellWindow ? shellWindow.landingStageChipModel : []

                                    delegate: ToneChip {
                                        shellWindow: root.shellWindow
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        tone: String(modelData["tone"] || "neutral")
                                    }
                                }
                            }

                            PanelFrame {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredHeight: stagePreferredHeight
                                shellWindow: root.shellWindow
                                panelColor: shellWindow ? shellWindow.surfaceQuiet : "#0d1822"
                                borderTone: shellWindow ? shellWindow.borderStrong : "#5fa0ce"
                                accentTone: shellWindow ? shellWindow.accentIce : "#87ddff"

                                WorldMapStage {
                                    anchors.fill: parent
                                    shellWindow: root.shellWindow
                                    trackData: root.trackData
                                    currentPoint: root.currentPoint
                                    headingDeg: root.headingDeg
                                    currentLabel: shellWindow ? shellWindow.landingMapBannerTitle : "M9-DEMO · FT-AIR-01"
                                    currentDetail: shellWindow ? shellWindow.landingMapBannerText : ""
                                    anchorLabel: String(liveAnchor["valid_instance"] || "--")
                                    scenarioLabel: shellWindow ? shellWindow.recommendedScenarioId : "--"
                                    scenarioTone: shellWindow ? shellWindow.liveAnchorTone : "neutral"
                                    landingMode: true
                                    stageActive: shellWindow ? shellWindow.currentPage === 0 : true
                                    bannerChips: shellWindow ? shellWindow.landingStageChipModel : []
                                    showInfoPanels: true
                                    preferBottomBannerDock: true
                                }
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: singleColumn ? 1 : 2
                                columnSpacing: shellWindow ? shellWindow.compactGap : 8
                                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: shellWindow ? shellWindow.landingTelemetryModel : []

                                    delegate: MetricTile {
                                        shellWindow: root.shellWindow
                                        Layout.fillWidth: true
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        detail: String(modelData["detail"] || "")
                                        tone: String(modelData["tone"] || "neutral")
                                    }
                                }
                            }
                        }

                        ShellCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: sideRailWidth
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                            eyebrow: "STRATEGY RAIL"
                            title: "弱网策略"
                            subtitle: compact(String(recommendedScenario["operator_note"] || recommendedScenario["summary"] || "右舷策略轨承接推荐档位、在线锚点和吞吐对照。"), compactPage ? 68 : 96)

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 1
                                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: root.weakOverviewModel

                                    delegate: MetricTile {
                                        shellWindow: root.shellWindow
                                        Layout.fillWidth: true
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        detail: String(modelData["detail"] || "")
                                        tone: String(modelData["tone"] || "neutral")
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "快速跳转"
                                color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 1
                                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: shellWindow ? shellWindow.landingJumpModel : []

                                    delegate: Rectangle {
                                        readonly property var jumpData: modelData
                                        radius: shellWindow ? shellWindow.edgeRadius : 14
                                        color: shellWindow ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.8) : "#0d1822"
                                        border.color: shellWindow
                                            ? Qt.rgba(shellWindow.toneColor(String(jumpData["tone"] || "neutral")).r, shellWindow.toneColor(String(jumpData["tone"] || "neutral")).g, shellWindow.toneColor(String(jumpData["tone"] || "neutral")).b, 0.38)
                                            : "#5fa0ce"
                                        border.width: 1
                                        Layout.fillWidth: true
                                        implicitHeight: jumpColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellWindow) shellWindow.currentPage = Number(jumpData["index"] || 0)
                                        }

                                        ColumnLayout {
                                            id: jumpColumn
                                            anchors.fill: parent
                                            anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                                            spacing: shellWindow ? shellWindow.scaled(2) : 2

                                            Text {
                                                text: String(jumpData["label"] || "--") + " / " + String(jumpData["english"] || "")
                                                color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                                font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                                                font.weight: Font.DemiBold
                                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                            }

                                            Text {
                                                text: String(jumpData["summary"] || "")
                                                color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                            }

                                            Text {
                                                text: String(jumpData["value"] || "")
                                                color: shellWindow ? shellWindow.toneColor(String(jumpData["tone"] || "neutral")) : "#87ddff"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                                font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    ShellCard {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                        eyebrow: "LIVE COMMAND TRAY"
                        title: "首页主动作"
                        subtitle: "先在这里点主动作，右侧摘要会同步回显；需要更多对照和恢复时再切换到执行页。"

                        GridLayout {
                            Layout.fillWidth: true
                            columns: singleColumn ? 1 : 4
                            columnSpacing: shellWindow ? shellWindow.zoneGap : 16
                            rowSpacing: shellWindow ? shellWindow.compactGap : 8

                            Repeater {
                                model: root.primaryActions

                                delegate: OperatorActionButton {
                                    shellWindow: root.shellWindow
                                    Layout.fillWidth: true
                                    actionData: modelData
                                    compact: true
                                }
                            }

                            InsetPanel {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                accentColor: shellWindow ? shellWindow.toneColor(String(shellWindow.lastActionResult["tone"] || "neutral")) : "#87ddff"
                                prominent: true

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: shellWindow ? shellWindow.scaled(4) : 4

                                    Text {
                                        text: "最近反馈"
                                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: String(shellWindow && shellWindow.lastActionResult ? shellWindow.lastActionResult["headline"] || "点击主动作后，这里会显示最近一次回执。" : "")
                                        color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 18
                                        font.weight: Font.DemiBold
                                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        visible: shellWindow && String(shellWindow.lastActionResult["detail"] || "").length > 0
                                        Layout.fillWidth: true
                                        text: String(shellWindow.lastActionResult["detail"] || "")
                                        color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: systemColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: systemColumn
                    width: parent.width
                    spacing: shellWindow ? shellWindow.zoneGap : 16

                    GridLayout {
                        Layout.fillWidth: true
                        columns: singleColumn ? 1 : 2
                        columnSpacing: shellWindow ? shellWindow.zoneGap : 16
                        rowSpacing: shellWindow ? shellWindow.zoneGap : 16

                        ShellCard {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentBlue : "#78b8e0"
                            eyebrow: "SYSTEM HEALTH"
                            title: "系统板态"
                            subtitle: shellWindow ? shellWindow.currentPageSummary : ""

                            GridLayout {
                                Layout.fillWidth: true
                                columns: singleColumn ? 1 : 2
                                columnSpacing: shellWindow ? shellWindow.compactGap : 8
                                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: root.statusRows

                                    delegate: MetricTile {
                                        shellWindow: root.shellWindow
                                        Layout.fillWidth: true
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        detail: "状态语义: " + String(modelData["tone"] || "neutral")
                                        tone: String(modelData["tone"] || "neutral")
                                    }
                                }
                            }
                        }

                        ShellCard {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                            eyebrow: "BOUNDARY"
                            title: "事实边界与启动入口"
                            subtitle: "系统页收口 repo-backed snapshot、launch hint 和当前动作反馈。"

                            InsetPanel {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: shellWindow ? shellWindow.scaled(4) : 4

                                    Text {
                                        text: "Truth Note"
                                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: shellWindow ? shellWindow.truthNoteValue : ""
                                        color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                        font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            InsetPanel {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                minimalChrome: true
                                accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: shellWindow ? shellWindow.scaled(4) : 4

                                    Text {
                                        text: "Launch Hint"
                                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: shellWindow ? shellWindow.launchHint : "--"
                                        color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                        wrapMode: Text.WrapAnywhere
                                    }
                                }
                            }

                            InsetPanel {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                accentColor: shellWindow ? shellWindow.toneColor(String(shellWindow.lastActionResult["tone"] || "neutral")) : "#87ddff"

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: shellWindow ? shellWindow.scaled(4) : 4

                                    Text {
                                        text: "Latest Action"
                                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: String(shellWindow && shellWindow.lastActionResult ? shellWindow.lastActionResult["headline"] || "当前还没有动作回执。" : "")
                                        color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 18
                                        font.weight: Font.DemiBold
                                        font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: flightColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: flightColumn
                    width: parent.width
                    spacing: shellWindow ? shellWindow.zoneGap : 16

                    GridLayout {
                        Layout.fillWidth: true
                        columns: singleColumn ? 1 : 2
                        columnSpacing: shellWindow ? shellWindow.zoneGap : 16
                        rowSpacing: shellWindow ? shellWindow.zoneGap : 16

                        ShellCard {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"
                            eyebrow: "FLIGHT STAGE"
                            title: shellWindow ? shellWindow.missionCallSignValue + " · 中国飞行态势板" : "Flight Stage"
                            subtitle: shellWindow ? shellWindow.activeSourceLabel + " · " + shellWindow.coordinatePair(currentPoint) : ""

                            PanelFrame {
                                Layout.fillWidth: true
                                Layout.preferredHeight: flightStageHeight
                                shellWindow: root.shellWindow
                                panelColor: shellWindow ? shellWindow.surfaceQuiet : "#0d1822"
                                borderTone: shellWindow ? shellWindow.borderStrong : "#5fa0ce"
                                accentTone: shellWindow ? shellWindow.accentIce : "#87ddff"

                                WorldMapStage {
                                    anchors.fill: parent
                                    shellWindow: root.shellWindow
                                    trackData: root.trackData
                                    currentPoint: root.currentPoint
                                    headingDeg: root.headingDeg
                                    currentLabel: shellWindow ? shellWindow.missionCallSignValue + " · " + shellWindow.aircraftIdValue : "M9-DEMO · FT-AIR-01"
                                    currentDetail: shellWindow ? shellWindow.activeSourceLabel + " · " + shellWindow.coordinatePair(currentPoint) : ""
                                    anchorLabel: String(liveAnchor["valid_instance"] || "--")
                                    scenarioLabel: shellWindow ? shellWindow.recommendedScenarioId : "--"
                                    scenarioTone: shellWindow ? shellWindow.liveAnchorTone : "neutral"
                                    landingMode: false
                                    stageActive: shellWindow ? shellWindow.currentPage === 2 : true
                                    bannerChips: [
                                        {
                                            "label": "链路",
                                            "value": shellWindow ? shellWindow.linkProfileValue : "--",
                                            "tone": "neutral"
                                        },
                                        {
                                            "label": "航迹",
                                            "value": String(trackData.length) + " 节点",
                                            "tone": trackData.length > 1 ? "online" : "neutral"
                                        },
                                        {
                                            "label": "锚点",
                                            "value": String(liveAnchor["valid_instance"] || "--"),
                                            "tone": shellWindow ? shellWindow.liveAnchorTone : "neutral"
                                        }
                                    ]
                                    showInfoPanels: true
                                    preferBottomBannerDock: false
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: shellWindow ? shellWindow.zoneGap : 16

                            ShellCard {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                accentColor: shellWindow ? shellWindow.accentBlue : "#78b8e0"
                                eyebrow: "CONTRACT"
                                title: "飞行合同"
                                subtitle: "把位置来源、采样时间、接口和回退语义收口到同一页。"

                                Repeater {
                                    model: root.flightContractModel

                                    delegate: MetricTile {
                                        shellWindow: root.shellWindow
                                        Layout.fillWidth: true
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        detail: String(modelData["detail"] || "")
                                        tone: String(modelData["tone"] || "neutral")
                                    }
                                }
                            }

                            ShellCard {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                                eyebrow: "TELEMETRY"
                                title: "遥测与定位质量"
                                subtitle: "页面会明确标注位置来源，不把 stub telemetry 伪装成实时 GPS。"

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 1
                                    rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                    Repeater {
                                        model: shellWindow ? shellWindow.landingTelemetryModel : []

                                        delegate: MetricTile {
                                            shellWindow: root.shellWindow
                                            Layout.fillWidth: true
                                            label: String(modelData["label"] || "--")
                                            value: String(modelData["value"] || "--")
                                            detail: String(modelData["detail"] || "")
                                            tone: String(modelData["tone"] || "neutral")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: weakColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: weakColumn
                    width: parent.width
                    spacing: shellWindow ? shellWindow.zoneGap : 16

                    GridLayout {
                        Layout.fillWidth: true
                        columns: singleColumn ? 1 : 2
                        columnSpacing: shellWindow ? shellWindow.zoneGap : 16
                        rowSpacing: shellWindow ? shellWindow.zoneGap : 16

                        ShellCard {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentGold : "#d9a15a"
                            eyebrow: "RECOMMENDED PLAYBOOK"
                            title: shellWindow ? shellWindow.recommendedScenarioId : "--"
                            subtitle: compact(String(recommendedScenario["summary"] || recommendedScenario["operator_note"] || "推荐剧本尚未返回更多说明。"), compactPage ? 72 : 110)

                            GridLayout {
                                Layout.fillWidth: true
                                columns: singleColumn ? 1 : 2
                                columnSpacing: shellWindow ? shellWindow.compactGap : 8
                                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: root.weakOverviewModel

                                    delegate: MetricTile {
                                        shellWindow: root.shellWindow
                                        Layout.fillWidth: true
                                        label: String(modelData["label"] || "--")
                                        value: String(modelData["value"] || "--")
                                        detail: String(modelData["detail"] || "")
                                        tone: String(modelData["tone"] || "neutral")
                                    }
                                }
                            }

                            InsetPanel {
                                Layout.fillWidth: true
                                shellWindow: root.shellWindow
                                accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"
                                minimalChrome: true

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: shellWindow ? shellWindow.scaled(4) : 4

                                    Text {
                                        text: "Stage Timing"
                                        color: shellWindow ? shellWindow.textMuted : "#5f7384"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 12
                                        font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                    }

                                    Repeater {
                                        model: shellWindow ? shellWindow.previewItems(stageTimingList, 4) : []

                                        delegate: Text {
                                            Layout.fillWidth: true
                                            text: String(modelData["label"] || "--") + " · " + shellWindow.formattedMetric(modelData["mean_ms"], 1, "ms")
                                            color: shellWindow ? shellWindow.textPrimary : "#d1deea"
                                            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 12
                                            font.family: shellWindow ? shellWindow.monoFamily : "Monospace"
                                            wrapMode: Text.WordWrap
                                        }
                                    }
                                }
                            }
                        }

                        ShellCard {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            accentColor: shellWindow ? shellWindow.accentIce : "#87ddff"
                            eyebrow: "SCENARIO DECK"
                            title: "对照剧本"
                            subtitle: "吞吐 uplift、saved seconds 和证据数统一放在这里，方便答辩时快速切到对照叙述。"

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: scenarioList

                                    delegate: Rectangle {
                                        readonly property var scenario: DataUtils.objectOrEmpty(modelData)
                                        readonly property var comparison: root.scenarioComparison(scenario)
                                        readonly property string tone: String(scenario["tone"] || "neutral")

                                        Layout.fillWidth: true
                                        radius: shellWindow ? shellWindow.edgeRadius : 14
                                        color: shellWindow ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.78) : "#0d1822"
                                        border.color: shellWindow
                                            ? Qt.rgba(shellWindow.toneColor(tone).r, shellWindow.toneColor(tone).g, shellWindow.toneColor(tone).b, 0.34)
                                            : "#5fa0ce"
                                        border.width: 1
                                        implicitHeight: scenarioColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)

                                        ColumnLayout {
                                            id: scenarioColumn
                                            anchors.fill: parent
                                            anchors.margins: shellWindow ? shellWindow.scaled(12) : 12
                                            spacing: shellWindow ? shellWindow.scaled(4) : 4

                                            RowLayout {
                                                Layout.fillWidth: true

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: String(scenario["label"] || scenario["scenario_id"] || "--")
                                                    color: shellWindow ? shellWindow.textStrong : "#f1f7fb"
                                                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 16
                                                    font.weight: Font.DemiBold
                                                    font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                                }

                                                ToneChip {
                                                    shellWindow: root.shellWindow
                                                    label: "tone"
                                                    value: String(scenario["scenario_id"] || "--")
                                                    tone: tone
                                                }
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: compact(String(scenario["summary"] || scenario["operator_note"] || ""), compactPage ? 84 : 124)
                                                color: shellWindow ? shellWindow.textSecondary : "#91a8bb"
                                                font.pixelSize: shellWindow ? shellWindow.bodySize : 14
                                                font.family: shellWindow ? shellWindow.uiFamily : "Sans Serif"
                                                wrapMode: Text.WordWrap
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: shellWindow ? shellWindow.compactGap : 8

                                                ToneChip {
                                                    shellWindow: root.shellWindow
                                                    label: "throughput"
                                                    value: shellWindow ? shellWindow.formattedMetric(comparison["pipeline_images_per_sec"], 3, "img/s") : "--"
                                                    tone: "online"
                                                }

                                                ToneChip {
                                                    shellWindow: root.shellWindow
                                                    label: "uplift"
                                                    value: shellWindow ? shellWindow.formattedMetric(comparison["throughput_uplift_pct"], 3, "%") : "--"
                                                    tone: "warning"
                                                }

                                                ToneChip {
                                                    shellWindow: root.shellWindow
                                                    label: "evidence"
                                                    value: String(DataUtils.arrayOrEmpty(scenario["evidence"]).length) + " 项"
                                                    tone: "neutral"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: actionColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: actionColumn
                    width: parent.width
                    spacing: shellWindow ? shellWindow.zoneGap : 16

                    ActionStrip {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        panelData: shellWindow ? shellWindow.bottomPanelData : ({})
                    }
                }
            }
        }
    }
}
