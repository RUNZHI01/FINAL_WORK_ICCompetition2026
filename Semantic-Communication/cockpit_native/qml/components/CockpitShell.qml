import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

Item {
    id: root

    property var shellWindow: null

    readonly property var performanceHeadline: shellWindow ? DataUtils.objectOrEmpty(shellWindow.performanceHeadline) : ({})
    readonly property var demoFlow: shellWindow ? DataUtils.arrayOrEmpty(shellWindow.demoFlow) : []
    readonly property var positionSource: shellWindow ? DataUtils.objectOrEmpty(shellWindow.positionSource) : ({})
    readonly property var recommendedScenario: shellWindow ? DataUtils.objectOrEmpty(shellWindow.recommendedScenario) : ({})
    readonly property var recommendedComparison: shellWindow ? DataUtils.objectOrEmpty(shellWindow.recommendedComparison) : ({})
    readonly property var stageTimingList: DataUtils.arrayOrEmpty(recommendedScenario["stage_timings"])
    readonly property var evidenceList: DataUtils.arrayOrEmpty(recommendedScenario["evidence"])
    readonly property var scenarioDeck: shellWindow ? shellWindow.previewItems(shellWindow.rightScenarios, wideShell ? 4 : 3) : []
    readonly property var systemPreview: shellWindow ? shellWindow.previewItems(shellWindow.statusRows, mediumShell ? 4 : 3) : []
    readonly property var landingJumps: shellWindow ? shellWindow.landingJumpModel : []
    readonly property bool wideShell: shellWindow ? shellWindow.viewportWidth >= 1700 : width >= 1700
    readonly property bool splitLanding: shellWindow ? shellWindow.viewportWidth >= 2040 : width >= 2040
    readonly property bool mediumShell: shellWindow ? shellWindow.viewportWidth >= 1320 : width >= 1320
    readonly property bool compactShell: shellWindow ? shellWindow.viewportWidth < 1180 : width < 1180
    readonly property int stageHeight: shellWindow
        ? Math.max(shellWindow.scaled(compactShell ? 560 : 720), shellWindow.viewportHeight - shellWindow.scaled(270))
        : (wideShell ? 920 : 680)
    readonly property int railWidth: shellWindow ? shellWindow.scaled(wideShell ? 210 : 196) : 210

    function compact(text, limit) {
        if (shellWindow)
            return shellWindow.compactMessage(text, limit)
        var resolved = String(text || "")
        var maxLength = Math.max(8, Number(limit || 48))
        if (resolved.length <= maxLength)
            return resolved
        return resolved.slice(0, maxLength - 1) + "…"
    }

    function scenarioTone(scenario) {
        return String(DataUtils.objectOrEmpty(scenario)["tone"] || "neutral")
    }

    function scenarioSummary(scenario) {
        var resolved = DataUtils.objectOrEmpty(scenario)
        return String(resolved["summary"] || resolved["operator_note"] || "--")
    }

    function comparisonValue(scenario, key, decimals, suffix) {
        if (!shellWindow)
            return "--"
        var comparison = DataUtils.objectOrEmpty(DataUtils.objectOrEmpty(scenario)["comparison"])
        return shellWindow.formattedMetric(comparison[key], decimals, suffix)
    }

    function stageValue(stage) {
        if (!shellWindow)
            return "--"
        return shellWindow.formattedMetric(DataUtils.objectOrEmpty(stage)["mean_ms"], 1, "ms")
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: shellWindow ? shellWindow.sceneTop : "#07121d" }
            GradientStop { position: 0.48; color: shellWindow ? shellWindow.sceneMid : "#0b1724" }
            GradientStop { position: 1.0; color: shellWindow ? shellWindow.sceneBottom : "#060d14" }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            width: parent.width * 0.42
            height: parent.height * 0.34
            radius: width / 2
            x: parent.width * 0.58
            y: -height * 0.12
            color: shellWindow ? shellWindow.haloCool : "#2a5c7a"
            opacity: 0.08
        }

        Rectangle {
            width: parent.width * 0.3
            height: parent.height * 0.26
            radius: width / 2
            x: -width * 0.12
            y: parent.height * 0.64
            color: shellWindow ? shellWindow.haloWarm : "#5d6d88"
            opacity: 0.06
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: shellWindow ? shellWindow.shellPadding : 16
        spacing: shellWindow ? shellWindow.zoneGap : 12

        CockpitHeader {
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
                    spacing: shellWindow ? shellWindow.zoneGap : 12

                    Loader {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        sourceComponent: wideShell ? landingWideComponent : landingStackedComponent
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Loader {
                    anchors.fill: parent
                    sourceComponent: mediumShell ? flightWideComponent : flightStackedComponent
                }
            }

            Flickable {
                clip: true
                contentWidth: width
                contentHeight: actionColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: actionColumn
                    width: parent.width
                    spacing: shellWindow ? shellWindow.zoneGap : 12

                    ActionDeck {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        panelData: shellWindow ? shellWindow.bottomPanelData : ({})
                    }
                }
            }
        }
    }

    Component {
        id: landingWideComponent

        Item {
            implicitHeight: root.stageHeight

            PanelFrame {
                anchors.fill: parent
                shellWindow: root.shellWindow
                panelColor: shellWindow ? shellWindow.surfaceGlass : "#1b2935"
                borderTone: shellWindow ? shellWindow.borderStrong : "#4e6c84"
                accentTone: shellWindow ? shellWindow.accentIce : "#86c7d4"

                WorldMapStageCanvas {
                    anchors.fill: parent
                    anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                    shellWindow: root.shellWindow
                    backdropMode: "asset"
                    backdropSource: shellWindow ? String(shellWindow.options["worldMapBackdropSource"] || "") : ""
                    trackData: shellWindow ? shellWindow.trackData : []
                    currentPoint: shellWindow ? shellWindow.currentPosition : ({})
                    headingDeg: shellWindow ? Number(shellWindow.kinematics["heading_deg"] || 0) : 0
                    currentLabel: ""
                    currentDetail: ""
                    anchorLabel: String(shellWindow ? shellWindow.liveAnchor["valid_instance"] || "--" : "--")
                    scenarioLabel: ""
                    scenarioTone: shellWindow ? shellWindow.liveAnchorTone : "neutral"
                    landingMode: true
                    preloadAssets: true
                    showInfoPanels: false
                    showStageBadge: false
                    showScenarioBadge: false
                    bannerEyebrow: ""
                    bannerTitle: ""
                    bannerText: ""
                    bannerChips: []
                }

                ShellCard {
                    width: root.railWidth
                    height: implicitHeight
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.leftMargin: shellWindow ? shellWindow.scaled(14) : 14
                    anchors.topMargin: shellWindow ? shellWindow.scaled(14) : 14
                    shellWindow: root.shellWindow
                    fillColor: shellWindow ? shellWindow.surfaceQuiet : "#111b24"
                    accentColor: shellWindow ? shellWindow.accentIce : "#86c7d4"
                    minimalChrome: true
                    eyebrow: "SYSTEM RAIL"
                    title: "系统"
                    padding: shellWindow ? shellWindow.scaled(8) : 8
                    contentSpacing: shellWindow ? shellWindow.scaled(5) : 5

                    Repeater {
                        model: shellWindow ? shellWindow.previewItems(root.systemPreview, 3) : []

                        delegate: InspectorRow {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            label: String(modelData["label"] || "--")
                            value: String(modelData["value"] || "--")
                            detail: String(modelData["detail"] || "")
                            tone: String(modelData["tone"] || "neutral")
                            prominent: index === 0
                            dividerVisible: index < 2
                        }
                    }
                }

                ShellCard {
                    id: landingInspector
                    width: root.railWidth
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.rightMargin: shellWindow ? shellWindow.scaled(14) : 14
                    anchors.topMargin: shellWindow ? shellWindow.scaled(14) : 14
                    anchors.bottomMargin: shellWindow ? shellWindow.scaled(14) : 14
                    shellWindow: root.shellWindow
                    fillColor: shellWindow ? shellWindow.surfaceQuiet : "#111b24"
                    accentColor: shellWindow ? shellWindow.accentGold : "#c9a06b"
                    minimalChrome: true
                    eyebrow: "LINK + SOURCE"
                    title: "剧本与边界"
                    padding: shellWindow ? shellWindow.scaled(8) : 8
                    contentSpacing: shellWindow ? shellWindow.scaled(5) : 5

                    InspectorRow {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "剧本"
                        value: compact(String(recommendedScenario["label"] || recommendedScenario["scenario_id"] || "--"), 18)
                        detail: compact(root.scenarioSummary(recommendedScenario), 38)
                        tone: root.scenarioTone(recommendedScenario)
                        prominent: true
                        dividerVisible: true
                    }

                    InspectorRow {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "吞吐"
                        value: root.comparisonValue(recommendedScenario, "pipeline_images_per_sec", 3, "img/s")
                        detail: "提升 " + root.comparisonValue(recommendedScenario, "throughput_uplift_pct", 3, "%")
                        tone: "online"
                        prominent: false
                        dividerVisible: true
                    }

                    InspectorRow {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "数据源"
                        value: compact(String(positionSource["label"] || "--"), 18)
                        detail: String(positionSource["configured_by"] || "")
                        tone: String(positionSource["status"] || "") === "stub" ? "warning" : "online"
                        dividerVisible: false
                    }
                }

            }
        }
    }

    Component {
        id: landingStackedComponent

        ColumnLayout {
            implicitHeight: topLandingStage.implicitHeight + landingBottomGrid.implicitHeight + spacing
            spacing: shellWindow ? shellWindow.zoneGap : 12

            PanelFrame {
                id: topLandingStage
                Layout.fillWidth: true
                implicitHeight: root.stageHeight
                shellWindow: root.shellWindow
                panelColor: shellWindow ? shellWindow.surfaceGlass : "#1b2935"
                borderTone: shellWindow ? shellWindow.borderStrong : "#4e6c84"
                accentTone: shellWindow ? shellWindow.accentIce : "#86c7d4"

                WorldMapStageCanvas {
                    anchors.fill: parent
                    anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                    shellWindow: root.shellWindow
                    backdropMode: "asset"
                    backdropSource: shellWindow ? String(shellWindow.options["worldMapBackdropSource"] || "") : ""
                    trackData: shellWindow ? shellWindow.trackData : []
                    currentPoint: shellWindow ? shellWindow.currentPosition : ({})
                    headingDeg: shellWindow ? Number(shellWindow.kinematics["heading_deg"] || 0) : 0
                    currentLabel: ""
                    currentDetail: ""
                    anchorLabel: shellWindow ? String(shellWindow.liveAnchor["valid_instance"] || "--") : "--"
                    scenarioLabel: shellWindow ? shellWindow.recommendedScenarioId : "--"
                    scenarioTone: shellWindow ? shellWindow.liveAnchorTone : "neutral"
                    landingMode: true
                    preloadAssets: true
                    showStageBadge: false
                    showScenarioBadge: false
                    preferBottomBannerDock: true
                    showInfoPanels: false
                    bannerEyebrow: ""
                    bannerTitle: ""
                    bannerText: ""
                    bannerChips: []
                }
            }

            GridLayout {
                id: landingBottomGrid
                Layout.fillWidth: true
                columns: compactShell ? 1 : 2
                columnSpacing: shellWindow ? shellWindow.zoneGap : 12
                rowSpacing: shellWindow ? shellWindow.zoneGap : 12

                ShellCard {
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    accentColor: shellWindow ? shellWindow.accentIce : "#86c7d4"
                    eyebrow: "SYSTEM RAIL"
                    title: "系统稳态"
                    subtitle: shellWindow ? shellWindow.landingSummaryText : ""

                    Repeater {
                        model: root.systemPreview

                        delegate: MetricTile {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
                            label: String(modelData["label"] || "--")
                            value: String(modelData["value"] || "--")
                            detail: "tone " + String(modelData["tone"] || "neutral")
                            tone: String(modelData["tone"] || "neutral")
                        }
                    }
                }

                ShellCard {
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    accentColor: shellWindow ? shellWindow.accentGold : "#c9a06b"
                    eyebrow: "WEAK-LINK"
                    title: String(recommendedScenario["label"] || recommendedScenario["scenario_id"] || "推荐剧本")
                    subtitle: root.compact(root.scenarioSummary(recommendedScenario), 72)

                    MetricTile {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "Pipeline"
                        value: root.comparisonValue(recommendedScenario, "pipeline_images_per_sec", 3, "img/s")
                        detail: "serial " + root.comparisonValue(recommendedScenario, "serial_images_per_sec", 3, "img/s")
                        tone: "online"
                        prominent: true
                    }

                    MetricTile {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "数据来源"
                        value: String(positionSource["label"] || "--")
                        detail: String(positionSource["summary"] || "")
                        tone: String(positionSource["status"] || "") === "stub" ? "warning" : "online"
                    }
                }
            }
        }
    }

    Component {
        id: flightWideComponent

        Item {
            implicitHeight: root.stageHeight

            PanelFrame {
                anchors.fill: parent
                shellWindow: root.shellWindow
                panelColor: shellWindow ? shellWindow.surfaceGlass : "#1b2935"
                borderTone: shellWindow ? shellWindow.borderStrong : "#4e6c84"
                accentTone: shellWindow ? shellWindow.accentIce : "#86c7d4"

                WorldMapStageCanvas {
                    anchors.fill: parent
                    anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                    shellWindow: root.shellWindow
                    backdropMode: "asset"
                    backdropSource: shellWindow ? String(shellWindow.options["worldMapBackdropSource"] || "") : ""
                    trackData: shellWindow ? shellWindow.trackData : []
                    currentPoint: shellWindow ? shellWindow.currentPosition : ({})
                    headingDeg: shellWindow ? Number(shellWindow.kinematics["heading_deg"] || 0) : 0
                    currentLabel: ""
                    currentDetail: ""
                    anchorLabel: String(shellWindow ? shellWindow.liveAnchor["valid_instance"] || "--" : "--")
                    scenarioLabel: ""
                    scenarioTone: shellWindow ? shellWindow.liveAnchorTone : "neutral"
                    preloadAssets: true
                    showStageBadge: false
                    showScenarioBadge: false
                    showInfoPanels: false
                    bannerChips: []
                    bannerEyebrow: ""
                    bannerTitle: ""
                    bannerText: ""
                }

                ShellCard {
                    width: root.railWidth + (shellWindow ? shellWindow.scaled(30) : 30)
                    height: implicitHeight
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.margins: shellWindow ? shellWindow.scaled(14) : 14
                    shellWindow: root.shellWindow
                    fillColor: shellWindow ? shellWindow.surfaceQuiet : "#111b24"
                    accentColor: shellWindow ? shellWindow.accentBlue : "#6eb9e7"
                    minimalChrome: true
                    eyebrow: "CONTRACT INSPECTOR"
                    title: "数据与来源"
                    padding: shellWindow ? shellWindow.scaled(8) : 8
                    contentSpacing: shellWindow ? shellWindow.scaled(5) : 5

                    InspectorRow {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "数据源"
                        value: compact(String(positionSource["label"] || "--"), 18)
                        detail: compact(String(positionSource["summary"] || ""), 46)
                        tone: "neutral"
                        prominent: true
                        dividerVisible: true
                    }

                    InspectorRow {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "接口"
                        value: shellWindow ? shellWindow.activeSourceLabel : "--"
                        detail: String(positionSource["api_path"] || "--")
                        tone: "neutral"
                        dividerVisible: true
                    }

                    InspectorRow {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "位置来源"
                        value: String(positionSource["coordinate_text"] || "--")
                        detail: String(positionSource["configured_by"] || "")
                        tone: String(positionSource["status"] || "") === "stub" ? "warning" : "online"
                        dividerVisible: false
                    }
                }

                Rectangle {
                    width: parent.width - (root.railWidth + (shellWindow ? shellWindow.scaled(44) : 44))
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: shellWindow ? shellWindow.scaled(14) : 14
                    anchors.rightMargin: root.railWidth + (shellWindow ? shellWindow.scaled(28) : 28)
                    anchors.bottomMargin: shellWindow ? shellWindow.scaled(14) : 14
                    radius: shellWindow ? shellWindow.edgeRadius : 12
                    color: shellWindow ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, 0.42) : "#111b24"
                    border.color: shellWindow ? Qt.rgba(shellWindow.borderSubtle.r, shellWindow.borderSubtle.g, shellWindow.borderSubtle.b, 0.18) : "#405463"
                    border.width: 1
                    implicitHeight: flightMetricFlow.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                    Flow {
                        id: flightMetricFlow
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        Repeater {
                            model: shellWindow ? shellWindow.landingTelemetryModel : []

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
        }
    }

    Component {
        id: flightStackedComponent

        ColumnLayout {
            implicitHeight: topFlightStage.implicitHeight + flightBottomGrid.implicitHeight + spacing
            spacing: shellWindow ? shellWindow.zoneGap : 12

            PanelFrame {
                id: topFlightStage
                Layout.fillWidth: true
                implicitHeight: root.stageHeight
                shellWindow: root.shellWindow
                panelColor: shellWindow ? shellWindow.surfaceGlass : "#1b2935"
                borderTone: shellWindow ? shellWindow.borderStrong : "#4e6c84"
                accentTone: shellWindow ? shellWindow.accentIce : "#86c7d4"

                WorldMapStageCanvas {
                    anchors.fill: parent
                    anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                    shellWindow: root.shellWindow
                    backdropMode: "asset"
                    backdropSource: shellWindow ? String(shellWindow.options["worldMapBackdropSource"] || "") : ""
                    trackData: shellWindow ? shellWindow.trackData : []
                    currentPoint: shellWindow ? shellWindow.currentPosition : ({})
                    headingDeg: shellWindow ? Number(shellWindow.kinematics["heading_deg"] || 0) : 0
                    currentLabel: ""
                    currentDetail: ""
                    anchorLabel: shellWindow ? String(shellWindow.liveAnchor["valid_instance"] || "--") : "--"
                    scenarioLabel: shellWindow ? shellWindow.recommendedScenarioId : "--"
                    scenarioTone: shellWindow ? shellWindow.liveAnchorTone : "neutral"
                    preloadAssets: true
                    showStageBadge: false
                    showScenarioBadge: false
                    showInfoPanels: false
                    bannerEyebrow: ""
                    bannerTitle: ""
                    bannerText: ""
                    bannerChips: []
                }
            }

            GridLayout {
                id: flightBottomGrid
                Layout.fillWidth: true
                columns: compactShell ? 1 : 2
                columnSpacing: shellWindow ? shellWindow.zoneGap : 12
                rowSpacing: shellWindow ? shellWindow.zoneGap : 12

                ShellCard {
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    accentColor: shellWindow ? shellWindow.accentBlue : "#6eb9e7"
                    eyebrow: "SOURCE CONTRACT"
                    title: String(positionSource["label"] || "--")
                    subtitle: String(positionSource["summary"] || "")

                    MetricTile {
                        Layout.fillWidth: true
                        shellWindow: root.shellWindow
                        label: "接口"
                        value: shellWindow ? shellWindow.activeSourceLabel : "--"
                        detail: String(positionSource["api_path"] || "--")
                        tone: "neutral"
                    }
                }

                ShellCard {
                    Layout.fillWidth: true
                    shellWindow: root.shellWindow
                    accentColor: shellWindow ? shellWindow.accentIce : "#86c7d4"
                    eyebrow: "TELEMETRY"
                    title: "飞行遥测"
                    subtitle: "当前位置与动力学指标。"

                    Repeater {
                        model: shellWindow ? shellWindow.landingTelemetryModel : []

                        delegate: MetricTile {
                            Layout.fillWidth: true
                            shellWindow: root.shellWindow
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
