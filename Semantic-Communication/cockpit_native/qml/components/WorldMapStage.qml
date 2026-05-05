import QtQuick 2.15

Item {
    id: root

    property var shellWindow: null
    property var trackData: []
    property var currentPoint: ({})
    property real headingDeg: 0
    property string currentLabel: "实时航迹"
    property string currentDetail: ""
    property string anchorLabel: "--"
    property string projectionLabel: "经纬投影 / EQUIRECTANGULAR"
    property string scenarioLabel: ""
    property string scenarioTone: "neutral"
    property bool landingMode: false
    property bool stageActive: true
    property bool preloadAssets: false
    property string bannerEyebrow: landingMode ? "全球指挥主舞台 / GLOBAL COMMAND STAGE" : "实时指挥舞台 / LIVE COMMAND STAGE"
    property string bannerTitle: currentLabel && currentLabel.length > 0
        ? currentLabel
        : (landingMode ? "世界主墙板" : "实时航迹")
    property string bannerText: currentDetail && currentDetail.length > 0
        ? currentDetail
        : "世界地图主墙板"
    property var bannerChips: []
    property bool showStageBadge: true
    property bool showScenarioBadge: true
    property bool showInfoPanels: true
    property bool preferBottomBannerDock: false

    readonly property var launchOptions: shellWindow && shellWindow.options ? shellWindow.options : ({})
    readonly property string requestedMapBackend: normalizeBackend(String(launchOptions["mapBackend"] || "auto"))
    readonly property string requestedMapProvider: String(launchOptions["mapProvider"] || "auto")
    readonly property var qtLocationProviders: launchOptions["qtLocationProviders"] || []
    readonly property string qtLocationPluginName: String(launchOptions["qtLocationPluginName"] || "")
    readonly property bool qtLocationAvailable: !!launchOptions["qtLocationAvailable"]
    readonly property bool qtPositioningAvailable: !!launchOptions["qtPositioningAvailable"]
    readonly property bool qtLocationStageAvailable: !!launchOptions["qtLocationStageAvailable"]
    readonly property bool qtLocationBackendReady: qtLocationAvailable
        && qtPositioningAvailable
        && qtLocationStageAvailable
        && qtLocationPluginName.length > 0
        && qtLocationProviders.indexOf(qtLocationPluginName) >= 0
    readonly property string worldMapBackdropSource: String(launchOptions["worldMapBackdropSource"] || "")
    readonly property bool localBackdropReady: worldMapBackdropSource.length > 0
    readonly property bool preferLandingBackdropBackend: landingMode
        && requestedMapBackend === "auto"
        && localBackdropReady
    readonly property bool compactStage: width < (landingMode ? 760 : 880)
    readonly property bool landingMinimalChrome: landingMode && !!(shellWindow ? shellWindow.landingStageMinimalChrome : true)
    readonly property bool landingTopBadgesVisible: shellWindow ? !!shellWindow.landingStageTopBadgesVisible : false
    readonly property int landingBannerChipLimit: resolveInt(
        shellWindow ? shellWindow.landingStageBannerChipLimit : (compactStage ? 1 : 2),
        compactStage ? 1 : 2
    )
    readonly property int landingBannerTitleLimit: resolveInt(
        shellWindow ? shellWindow.landingStageBannerTitleLimit : (compactStage ? 18 : 24),
        compactStage ? 18 : 24
    )
    readonly property int flightBannerChipLimit: resolveInt(
        shellWindow ? shellWindow.flightStageBannerChipLimit : bannerChips.length,
        bannerChips.length
    )
    readonly property int bannerChipLimit: landingMode ? landingBannerChipLimit : flightBannerChipLimit
    readonly property int landingBannerTextLimit: resolveInt(
        shellWindow ? shellWindow.landingStageBannerTextLimit : (compactStage ? 32 : 52),
        compactStage ? 32 : 52
    )
    readonly property string effectiveBannerText: landingMinimalChrome
        ? compactText(root.bannerText, landingBannerTextLimit)
        : root.bannerText
    readonly property string effectiveBannerEyebrow: landingMinimalChrome ? "" : root.bannerEyebrow
    readonly property string effectiveBannerTitle: landingMinimalChrome
        ? compactText(root.bannerTitle, landingBannerTitleLimit)
        : root.bannerTitle
    readonly property var effectiveBannerChips: limitedChips(root.bannerChips, bannerChipLimit)
    readonly property bool effectiveShowStageBadge: root.showStageBadge && (!landingMinimalChrome || landingTopBadgesVisible)
    readonly property bool effectiveShowScenarioBadge: root.showScenarioBadge && (!landingMinimalChrome || landingTopBadgesVisible)
    readonly property string activeMapBackend: resolvedMapBackend()

    function normalizeBackend(value) {
        if (value === "canvas" || value === "svg" || value === "qtlocation")
            return value
        return "auto"
    }

    function resolveInt(value, fallback) {
        var resolved = Number(value)
        if (!isFinite(resolved))
            return Math.max(0, Number(fallback || 0))
        return Math.max(0, Math.round(resolved))
    }

    function compactText(text, limit) {
        var resolved = String(text || "")
        var maxLength = Math.max(0, resolveInt(limit, resolved.length))
        if (maxLength === 0 || resolved.length <= maxLength)
            return resolved
        return resolved.slice(0, Math.max(0, maxLength - 1)) + "…"
    }

    function limitedChips(chips, limit) {
        var resolved = chips && chips.length !== undefined ? chips : []
        var maxLength = resolveInt(limit, resolved.length)
        if (maxLength === 0 || resolved.length <= maxLength)
            return resolved
        return resolved.slice(0, maxLength)
    }

    function resolvedMapBackend() {
        if (requestedMapBackend === "canvas")
            return "canvas"
        if (requestedMapBackend === "qtlocation")
            return qtLocationBackendReady ? "qtlocation" : "canvas"
        if (requestedMapBackend === "svg")
            return localBackdropReady ? "svg" : "canvas"
        return "canvas"
    }

    Loader {
        id: stageLoader
        anchors.fill: parent
        source: root.activeMapBackend === "qtlocation"
            ? "WorldMapStageQtLocation.qml"
            : "WorldMapStageCanvas.qml"
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "shellWindow"
        value: root.shellWindow
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "trackData"
        value: root.trackData
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "currentPoint"
        value: root.currentPoint
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "headingDeg"
        value: root.headingDeg
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "currentLabel"
        value: root.currentLabel
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "currentDetail"
        value: root.currentDetail
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "anchorLabel"
        value: root.anchorLabel
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "projectionLabel"
        value: root.projectionLabel
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "scenarioLabel"
        value: root.scenarioLabel
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "scenarioTone"
        value: root.scenarioTone
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "landingMode"
        value: root.landingMode
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "stageActive"
        value: root.stageActive
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "preloadAssets"
        value: root.preloadAssets
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "bannerEyebrow"
        value: root.effectiveBannerEyebrow
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "bannerTitle"
        value: root.effectiveBannerTitle
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "bannerText"
        value: root.effectiveBannerText
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "bannerChips"
        value: root.effectiveBannerChips
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "showStageBadge"
        value: root.effectiveShowStageBadge
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "showScenarioBadge"
        value: root.effectiveShowScenarioBadge
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "showInfoPanels"
        value: root.showInfoPanels
    }

    Binding {
        when: stageLoader.item !== null
        target: stageLoader.item
        property: "preferBottomBannerDock"
        value: root.preferBottomBannerDock
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend !== "qtlocation"
        target: stageLoader.item
        property: "backdropMode"
        value: root.activeMapBackend === "svg" ? "asset" : "canvas"
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend !== "qtlocation"
        target: stageLoader.item
        property: "backdropSource"
        value: root.activeMapBackend === "svg" ? root.worldMapBackdropSource : ""
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend === "qtlocation"
        target: stageLoader.item
        property: "mapProvider"
        value: root.requestedMapProvider
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend === "qtlocation"
        target: stageLoader.item
        property: "pluginName"
        value: root.qtLocationPluginName
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend === "qtlocation"
        target: stageLoader.item
        property: "tileMode"
        value: String(root.launchOptions["mapTileMode"] || "online")
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend === "qtlocation"
        target: stageLoader.item
        property: "tileRoot"
        value: String(root.launchOptions["mapTileRoot"] || "")
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend === "qtlocation"
        target: stageLoader.item
        property: "tileFormat"
        value: String(root.launchOptions["mapTileFormat"] || "png")
    }

    Binding {
        when: stageLoader.item !== null && root.activeMapBackend === "qtlocation"
        target: stageLoader.item
        property: "backdropSource"
        value: root.worldMapBackdropSource
    }
}
