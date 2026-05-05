import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "components"
import "components/DataUtils.js" as DataUtils

ApplicationWindow {
    id: root

    readonly property bool bridgeAvailable: (typeof cockpitBridgeAvailable !== "undefined") && !!cockpitBridgeAvailable
    readonly property var uiState: DataUtils.jsonObjectOrEmpty((typeof cockpitUiStateJson !== "undefined") ? cockpitUiStateJson : "{}")
    readonly property var zones: DataUtils.objectOrEmpty(uiState["zones"])
    readonly property var metrics: DataUtils.objectOrEmpty((typeof screenMetrics !== "undefined") ? screenMetrics : null)
    readonly property var insets: DataUtils.objectOrEmpty((typeof safeAreaInsets !== "undefined") ? safeAreaInsets : null)
    readonly property var options: DataUtils.objectOrEmpty((typeof launchOptions !== "undefined") ? launchOptions : null)
    readonly property var themePalette: DataUtils.objectOrEmpty(options["themePalette"])

    readonly property var leftPanelData: DataUtils.objectOrEmpty(zones["left_status_panel"])
    readonly property var centerPanelData: DataUtils.objectOrEmpty(zones["center_tactical_view"])
    readonly property var rightPanelData: DataUtils.objectOrEmpty(zones["right_weak_network_panel"])
    readonly property var bottomPanelData: DataUtils.objectOrEmpty(zones["bottom_action_strip"])
    readonly property var bottomActions: DataUtils.arrayOrEmpty(bottomPanelData["actions"])
    readonly property var meta: DataUtils.objectOrEmpty(uiState["meta"])
    readonly property var demoStory: DataUtils.objectOrEmpty(meta["demo_story"])
    readonly property var performanceHeadline: DataUtils.objectOrEmpty(demoStory["performance_headline"])
    readonly property var demoFlow: DataUtils.arrayOrEmpty(demoStory["flow"])
    readonly property var statusRows: DataUtils.arrayOrEmpty(leftPanelData["rows"])
    readonly property var centerControlSummary: DataUtils.objectOrEmpty(centerPanelData["control_summary"])
    readonly property var centerFeedContract: DataUtils.objectOrEmpty(centerPanelData["feed_contract"])
    readonly property var trackData: DataUtils.arrayOrEmpty(centerPanelData["track"])
    readonly property var currentPosition: DataUtils.objectOrEmpty(centerPanelData["position"])
    readonly property var positionSource: DataUtils.objectOrEmpty(centerPanelData["position_source"])
    readonly property var kinematics: DataUtils.objectOrEmpty(centerPanelData["kinematics"])
    readonly property var fix: DataUtils.objectOrEmpty(centerPanelData["fix"])
    readonly property var liveAnchor: DataUtils.objectOrEmpty(rightPanelData["live_anchor"])
    readonly property var rightScenarios: DataUtils.arrayOrEmpty(rightPanelData["scenarios"])
    readonly property var recommendedScenario: recommendedScenarioObject(rightScenarios)
    readonly property var recommendedComparison: DataUtils.objectOrEmpty(recommendedScenario["comparison"])
    readonly property string recommendedScenarioId: String(
        rightPanelData["recommended_scenario_id"] || recommendedScenario["scenario_id"] || "--"
    )
    readonly property int enabledBottomActions: enabledActionTotal(bottomActions)
    readonly property bool softwareRenderEnabled: !!options["softwareRender"]
    readonly property var actionRuntime: (typeof cockpitBridge !== "undefined") && cockpitBridge
        ? DataUtils.objectOrEmpty(cockpitBridge.actionState)
        : ({})
    readonly property var lastActionResult: DataUtils.objectOrEmpty(actionRuntime["last_action"])
    readonly property bool actionBusy: !!actionRuntime["busy"]

    readonly property int designWidth: 2560
    readonly property int designHeight: 1440

    readonly property string displayFamily: String(options["displayFontFamily"] || options["uiFontFamily"] || "Ubuntu Sans")
    readonly property string uiFamily: String(options["uiFontFamily"] || "Ubuntu Sans")
    readonly property string monoFamily: String(options["monoFontFamily"] || "Ubuntu Sans Mono")

    readonly property color sceneTop: themeColor("sceneTop", "#07131d")
    readonly property color sceneMid: themeColor("sceneMid", "#0c1d2d")
    readonly property color sceneBottom: themeColor("sceneBottom", "#08131d")
    readonly property color haloCool: themeColor("haloCool", "#1f5f95")
    readonly property color haloWarm: themeColor("haloWarm", "#4d5f84")
    readonly property color shellExterior: themeColor("shellExterior", "#0b1620")
    readonly property color shellInterior: themeColor("shellInterior", "#142331")
    readonly property color surfaceRaised: themeColor("surfaceRaised", "#132434")
    readonly property color surfaceQuiet: themeColor("surfaceQuiet", "#0d1822")
    readonly property color surfaceGlass: themeColor("surfaceGlass", "#1a3144")
    readonly property color borderSubtle: themeColor("borderSubtle", "#274257")
    readonly property color borderStrong: themeColor("borderStrong", "#5fa0ce")
    readonly property color accentIce: themeColor("accentIce", "#87ddff")
    readonly property color accentGold: themeColor("accentGold", "#d9a15a")
    readonly property color accentMint: themeColor("accentMint", "#46d7a0")
    readonly property color accentRose: themeColor("accentRose", "#ff728b")
    readonly property color textStrong: themeColor("textStrong", "#f1f7fb")
    readonly property color textPrimary: themeColor("textPrimary", "#d1deea")
    readonly property color textSecondary: themeColor("textSecondary", "#91a8bb")
    readonly property color textMuted: themeColor("textMuted", "#5f7384")
    readonly property color dataLine: themeColor("dataLine", "#153043")
    readonly property color dataLineStrong: themeColor("dataLineStrong", "#244b63")
    readonly property color panelHighlight: themeColor("panelHighlight", "#1d4d6f")
    readonly property color panelGlowSoft: themeColor("panelGlowSoft", "#63c5f2")
    readonly property color canopyTop: themeColor("canopyTop", "#163247")
    readonly property color canopyBottom: themeColor("canopyBottom", "#0b141c")

    readonly property color panelColor: surfaceRaised
    readonly property color panelColorRaised: surfaceGlass
    readonly property color panelColorSoft: surfaceQuiet
    readonly property color cardColor: surfaceRaised
    readonly property color borderSoft: borderSubtle
    readonly property color accentBlue: themeColor("accentBlue", "#94bad8")
    readonly property color accentCyan: accentIce
    readonly property color accentAmber: accentGold
    readonly property color accentGreen: accentMint
    readonly property color accentRed: accentRose
    readonly property color gridLine: dataLine
    readonly property color gridLineStrong: dataLineStrong
    readonly property color shellDockTop: themeColor("shellDockTop", "#21394f")
    readonly property color shellDockMid: themeColor("shellDockMid", "#182637")
    readonly property color shellDockBottom: themeColor("shellDockBottom", "#101b27")
    readonly property color panelGlowStrong: panelGlowSoft
    readonly property color panelTraceStrong: borderStrong

    readonly property real widthScale: Math.max(0.82, Math.min(1.6, Number(metrics["width"] || designWidth) / designWidth))
    readonly property real heightScale: Math.max(0.82, Math.min(1.6, Number(metrics["height"] || designHeight) / designHeight))
    readonly property real uiScale: Math.min(widthScale, heightScale)

    readonly property int safeLeft: Number(insets["left"] || 0)
    readonly property int safeTop: Number(insets["top"] || 0)
    readonly property int safeRight: Number(insets["right"] || 0)
    readonly property int safeBottom: Number(insets["bottom"] || 0)

    readonly property int viewportHeight: height > 0 ? height : Number(metrics["height"] || designHeight)
    readonly property real viewportWidth: width > 0 ? width : Number(metrics["width"] || designWidth)
    readonly property real contentWidth: Math.max(1, viewportWidth - safeLeft - safeRight)
    readonly property bool wideLayout: viewportWidth >= 1680
    readonly property bool mediumLayout: !wideLayout && viewportWidth >= 1280
    readonly property bool compactLayout: !wideLayout && !mediumLayout
    readonly property bool shortViewport: viewportHeight < 940

    readonly property int outerPadding: scaled(compactLayout ? 12 : 18)
    readonly property int shellPadding: scaled(compactLayout ? 16 : 22)
    readonly property int zoneGap: scaled(compactLayout ? 12 : 18)
    readonly property int compactGap: scaled(compactLayout ? 8 : 10)
    readonly property int panelPadding: scaled(compactLayout ? 18 : 24)
    readonly property int cardPadding: scaled(compactLayout ? 14 : 18)
    readonly property int panelRadius: scaled(28)
    readonly property int cardRadius: scaled(20)
    readonly property int edgeRadius: scaled(15)
    readonly property int headerTitleSize: scaled(compactLayout ? 40 : 56)
    readonly property int sectionTitleSize: scaled(compactLayout ? 30 : 42)
    readonly property int bodyEmphasisSize: scaled(compactLayout ? 20 : 24)
    readonly property int bodySize: scaled(compactLayout ? 16 : 18)
    readonly property int captionSize: scaled(compactLayout ? 13 : 15)
    readonly property int eyebrowSize: scaled(compactLayout ? 12 : 14)

    readonly property string topTitle: primaryLabel(meta["title"] || "飞腾原生座舱")
    readonly property string topSubtitle: String(
        meta["subtitle"] || "Qt/QML 原生壳体继续读取仓库现有 TVM/OpenAMP 演示合同，并保持软件渲染安全启动。"
    )
    readonly property string activeSourceLabel: String(centerFeedContract["active_source_label"] || centerPanelData["source_label"] || "--")
    readonly property string systemSessionValue: String((statusRow("会话") || {})["value"] || "--")
    readonly property string recentEventValue: String((statusRow("最近事件") || {})["value"] || "--")
    readonly property string recentEventTone: recentEventValue.indexOf("REJECT") >= 0
        ? "warning"
        : String((statusRow("最近事件") || {})["tone"] || "neutral")
    readonly property string heartbeatValue: String((statusRow("心跳") || {})["value"] || "--")
    readonly property string heartbeatTone: String((statusRow("心跳") || {})["tone"] || "neutral")
    readonly property string linkProfileValue: String(centerControlSummary["link_profile"] || (statusRow("链路档位") || {})["value"] || "--")
    readonly property string snapshotReasonValue: String((statusRow("快照原因") || {})["value"] || "--")
    readonly property string truthNoteValue: String(leftPanelData["truth_note"] || rightPanelData["truth_note"] || "")
    readonly property string eventTimeValue: String((statusRow("事件时间") || {})["value"] || "--")
    readonly property string launchHint: String(meta["launch_hint"] || "bash ./session_bootstrap/scripts/run_cockpit_native.sh")
    readonly property string snapshotRelativePath: String(leftPanelData["snapshot_path"] || "--")
    readonly property string aircraftIdValue: String(centerPanelData["aircraft_id"] || "FT-AIR-01")
    readonly property string missionCallSignValue: String(centerPanelData["mission_call_sign"] || "M9-DEMO")
    readonly property string liveAnchorTone: String(liveAnchor["tone"] || "neutral")
    readonly property string landingSummaryTitle: recentEventTone === "warning"
        ? "异常回注态势墙"
        : "全球任务态势主墙"
    readonly property string landingSummaryText: String(centerControlSummary["last_event_message"] || rightPanelData["summary"] || topSubtitle)
    readonly property string landingMapBannerTitle: missionCallSignValue + " · " + aircraftIdValue
    readonly property string landingMapBannerText: coordinatePair(currentPosition) + " · "
        + formattedMetric(kinematics["ground_speed_kph"], 0, "km/h")
        + " · "
        + formattedMetric(kinematics["altitude_m"], 0, "m")
    readonly property string footerNote: String(
        bottomPanelData["footer_note"] || "默认执行仓库内软件渲染安全启动路径。"
    )
    readonly property string headlineCurrentValue: formattedMetric(performanceHeadline["current_ms"], 3, "ms")
    readonly property string headlineBaselineValue: formattedMetric(performanceHeadline["baseline_ms"], 1, "ms")
    readonly property string headlineImprovementValue: formattedMetric(performanceHeadline["improvement_pct"], 2, "%")
    readonly property string headlineSpeedupValue: formattedMetric(performanceHeadline["speedup_x"], 1, "x")
    readonly property string currentPageSummary: String(
        DataUtils.objectOrEmpty(navigationModel[currentPage])["summary"] || topSubtitle
    )

    property int currentPage: 0

    readonly property var navigationModel: [
        {
            "index": 0,
            "label": "态势",
            "english": "Situation",
            "summary": "任务地图主舞台、系统在线态与可信 headline。"
        },
        {
            "index": 1,
            "label": "合同",
            "english": "Contract",
            "summary": "飞行位置、数据来源、弱网策略与证据边界。"
        },
        {
            "index": 2,
            "label": "执行",
            "english": "Execute",
            "summary": "主动作、动作回执、板卡探测与恢复入口。"
        }
    ]

    readonly property var topStatusModel: [
        { "label": "会话", "value": systemSessionValue, "tone": "neutral" },
        { "label": "心跳", "value": heartbeatValue, "tone": heartbeatTone },
        { "label": "在线锚点", "value": String(liveAnchor["valid_instance"] || "--"), "tone": liveAnchorTone },
        { "label": "渲染模式", "value": softwareRenderEnabled ? "软件安全" : "图形优先", "tone": softwareRenderEnabled ? "warning" : "online" }
    ]

    readonly property var landingJumpModel: [
        {
            "index": 1,
            "label": "合同",
            "english": "Contract",
            "summary": "数据来源、飞行位置与弱网约束",
            "value": compactMessage(activeSourceLabel + " / " + recommendedScenarioId, compactLayout ? 18 : 30),
            "tone": "online"
        },
        {
            "index": 2,
            "label": "执行",
            "english": "Execute",
            "summary": "主动作、探板与回执",
            "value": String(enabledBottomActions) + " / " + String(bottomActions.length) + " 动作",
            "tone": enabledBottomActions > 0 ? "online" : "warning"
        }
    ]

    readonly property var landingTelemetryModel: [
        {
            "label": "当前位置",
            "value": coordinatePair(currentPosition),
            "detail": "WGS84 / 实时位置",
            "tone": "neutral"
        },
        {
            "label": "飞行高度",
            "value": formattedMetric(kinematics["altitude_m"], 0, "m"),
            "detail": "垂速 " + formattedMetric(kinematics["vertical_speed_mps"], 1, "m/s"),
            "tone": "online"
        },
        {
            "label": "地速与航向",
            "value": formattedMetric(kinematics["ground_speed_kph"], 0, "km/h"),
            "detail": "航向 " + formattedMetric(kinematics["heading_deg"], 0, "°"),
            "tone": "neutral"
        },
        {
            "label": "定位质量",
            "value": String(fix["type"] || "--") + " / " + formattedMetric(fix["satellites"], 0, "sat"),
            "detail": "置信 " + formattedMetric(fix["confidence_m"], 1, "m"),
            "tone": "online"
        }
    ]

    readonly property var landingWeakMetricModel: [
        {
            "label": "推荐剧本",
            "value": recommendedScenarioId,
            "detail": compactMessage(
                String(recommendedScenario["summary"] || "延续仓库现有弱网推荐剧本。"),
                compactLayout ? 26 : 44
            ),
            "tone": "warning"
        },
        {
            "label": "吞吐对照",
            "value": formattedMetric(recommendedComparison["pipeline_images_per_sec"], 3, "img/s"),
            "detail": "pipeline 对照",
            "tone": "online"
        },
        {
            "label": "提升幅度",
            "value": formattedMetric(recommendedComparison["throughput_uplift_pct"], 3, "%"),
            "detail": "弱网 uplift",
            "tone": "warning"
        },
        {
            "label": "在线锚点",
            "value": String(liveAnchor["valid_instance"] || "--"),
            "detail": compactMessage(String(liveAnchor["board_status"] || "等待在线锚点"), compactLayout ? 16 : 28),
            "tone": liveAnchorTone
        }
    ]

    readonly property var landingStageChipModel: [
        { "label": "数据源", "value": compactMessage(activeSourceLabel, compactLayout ? 18 : 24), "tone": "online" },
        { "label": "在线锚点", "value": String(liveAnchor["valid_instance"] || "--"), "tone": liveAnchorTone },
        { "label": "链路档位", "value": compactMessage(linkProfileValue, compactLayout ? 14 : 20), "tone": "neutral" }
    ]
    readonly property bool landingStageMinimalChrome: true
    readonly property bool landingStageTopBadgesVisible: false
    readonly property int landingStageBannerChipLimit: 1
    readonly property int landingStageBannerTextLimit: compactLayout ? 34 : 42
    readonly property int landingStageBannerTitleLimit: compactLayout ? 22 : 28
    readonly property int flightStageBannerChipLimit: 3

    readonly property var systemPageChipModel: [
        { "label": "会话", "value": systemSessionValue, "tone": "neutral" },
        { "label": "心跳", "value": heartbeatValue, "tone": heartbeatTone },
        { "label": "最近事件", "value": compactMessage(recentEventValue, compactLayout ? 12 : 18), "tone": recentEventTone },
        { "label": "链路", "value": compactMessage(linkProfileValue, compactLayout ? 12 : 18), "tone": "neutral" }
    ]

    readonly property var weakPageChipModel: [
        { "label": "推荐档", "value": recommendedScenarioId, "tone": "warning" },
        { "label": "吞吐", "value": formattedMetric(recommendedComparison["pipeline_images_per_sec"], 3, "img/s"), "tone": "online" },
        { "label": "提升", "value": formattedMetric(recommendedComparison["throughput_uplift_pct"], 3, "%"), "tone": "warning" },
        { "label": "锚点", "value": String(liveAnchor["valid_instance"] || "--"), "tone": liveAnchorTone }
    ]

    readonly property var actionPageChipModel: [
        { "label": "动作", "value": String(bottomActions.length), "tone": "neutral" },
        { "label": "可执行", "value": String(enabledBottomActions), "tone": enabledBottomActions > 0 ? "online" : "warning" },
        { "label": "仓库桥接", "value": bridgeAvailable ? "仓库在线" : "桥接缺失", "tone": bridgeAvailable ? "online" : "warning" },
        { "label": "渲染", "value": softwareRenderEnabled ? "软件安全" : "图形优先", "tone": softwareRenderEnabled ? "warning" : "online" }
    ]

    minimumWidth: 1024
    minimumHeight: 720
    flags: Qt.Window
    visible: true
    color: sceneBottom
    title: topTitle

    function scaled(value) {
        return Math.max(1, Math.round(value * uiScale))
    }

    function themeColor(name, fallback) {
        return themePalette[name] || fallback
    }

    function primaryLabel(text) {
        var raw = String(text || "")
        var slash = raw.indexOf("/")
        return slash >= 0 ? raw.slice(0, slash).trim() : raw
    }

    function statusRow(label) {
        for (var index = 0; index < statusRows.length; ++index) {
            var row = DataUtils.objectOrEmpty(statusRows[index])
            if (String(row["label"] || "") === label)
                return row
        }
        return ({})
    }

    function enabledActionTotal(actionsModel) {
        var actionList = DataUtils.arrayOrEmpty(actionsModel)
        var total = 0
        for (var index = 0; index < actionList.length; ++index) {
            var action = DataUtils.objectOrEmpty(actionList[index])
            if (!!action["enabled"])
                total += 1
        }
        return total
    }

    function toneColor(tone) {
        if (tone === "online")
            return accentMint
        if (tone === "offline" || tone === "danger")
            return accentRose
        if (tone === "warning" || tone === "degraded")
            return accentGold
        return accentIce
    }

    function toneFill(tone) {
        if (tone === "online")
            return "#0f2a22"
        if (tone === "offline" || tone === "danger")
            return "#2c161c"
        if (tone === "warning" || tone === "degraded")
            return "#2a2014"
        return "#122838"
    }

    function formattedMetric(value, decimals, suffix) {
        var resolved = Number(value)
        if (!isFinite(resolved))
            return "--"
        return resolved.toFixed(decimals) + (suffix ? (" " + suffix) : "")
    }

    function coordinatePair(point) {
        var resolved = DataUtils.objectOrEmpty(point)
        var latitude = Number(resolved["latitude"])
        var longitude = Number(resolved["longitude"])
        if (!isFinite(latitude) || !isFinite(longitude))
            return "--"
        return latitude.toFixed(3) + "°, " + longitude.toFixed(3) + "°"
    }

    function recommendedScenarioObject(scenariosModel) {
        var scenarioList = DataUtils.arrayOrEmpty(scenariosModel)
        var preferredScenarioId = String(rightPanelData["recommended_scenario_id"] || "")
        for (var index = 0; index < scenarioList.length; ++index) {
            var scenario = DataUtils.objectOrEmpty(scenarioList[index])
            if (!!scenario["recommended"] || String(scenario["scenario_id"] || "") === preferredScenarioId)
                return scenario
        }
        return scenarioList.length > 0 ? DataUtils.objectOrEmpty(scenarioList[0]) : ({})
    }

    function compactMessage(text, limit) {
        var resolved = String(text || "")
        var maxLength = Math.max(8, Number(limit || 40))
        if (resolved.length <= maxLength)
            return resolved
        return resolved.slice(0, maxLength - 1) + "…"
    }

    function previewItems(itemsModel, limit) {
        var resolved = DataUtils.arrayOrEmpty(itemsModel)
        if (resolved.length <= limit)
            return resolved
        return resolved.slice(0, limit)
    }

    function invokeOperatorAction(action) {
        var resolved = DataUtils.objectOrEmpty(action)
        var actionId = String(resolved["action_id"] || "")
        if (actionId.length === 0)
            return
        if ((typeof cockpitBridge === "undefined") || !cockpitBridge || !cockpitBridge.invokeAction)
            return
        cockpitBridge.invokeAction(
            actionId,
            String(resolved["api_path"] || ""),
            String(resolved["method"] || "POST"),
            String(resolved["label"] || actionId)
        )
    }

    Component.onCompleted: {
        var availableWidth = Math.max(minimumWidth, Number(metrics["width"] || designWidth))
        var availableHeight = Math.max(minimumHeight, Number(metrics["height"] || designHeight))
        var titleBarOffset = 40
        width = Math.max(minimumWidth, Math.round(availableWidth * 0.95))
        height = Math.max(minimumHeight, Math.round((availableHeight - titleBarOffset) * 0.94))
        x = Math.max(0, Math.round((availableWidth - width) / 2))
        y = Math.max(0, Math.round((availableHeight - height - titleBarOffset) / 2))
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.sceneTop }
            GradientStop { position: 0.46; color: root.sceneMid }
            GradientStop { position: 1.0; color: root.sceneBottom }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            width: parent.width * 0.5
            height: parent.height * 0.5
            radius: width / 2
            x: parent.width * 0.68
            y: -height * 0.22
            color: root.haloCool
            opacity: 0.06
        }

        Rectangle {
            width: parent.width * 0.4
            height: parent.height * 0.4
            radius: width / 2
            x: -width * 0.16
            y: parent.height * 0.62
            color: root.haloWarm
            opacity: 0.04
        }
    }

    CockpitShell {
        anchors.fill: parent
        shellWindow: root
    }
}
