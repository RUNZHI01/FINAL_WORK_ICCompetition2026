import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtLocation 6.5
import QtPositioning 6.5

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
        : "QtLocation 实时地图舞台"
    property var bannerChips: []
    property bool showStageBadge: true
    property bool showScenarioBadge: true
    property bool showInfoPanels: true
    property bool preferBottomBannerDock: false
    property string backdropSource: ""

    property string mapProvider: "auto"
    property string pluginName: "osm"
    property string tileMode: "online"
    property string tileRoot: ""
    property string tileFormat: "png"

    readonly property int mapInset: shellWindow ? shellWindow.scaled(landingMode ? 10 : 18) : (landingMode ? 10 : 18)
    readonly property int overlayMargin: shellWindow ? shellWindow.scaled(landingMode ? 11 : 16) : (landingMode ? 11 : 16)
    readonly property bool compactStage: width < 780
    readonly property bool stackedBanner: width < (landingMode ? 620 : 780)
    readonly property bool bannerDockedBottom: preferBottomBannerDock
        && width >= (shellWindow ? shellWindow.scaled(300) : 300)
    readonly property bool showTelemetryPanel: root.showInfoPanels && (!landingMode || !compactStage)
    readonly property bool hasCurrentPoint: isFinite(Number(currentPoint["longitude"])) && isFinite(Number(currentPoint["latitude"]))
    readonly property var currentCoordinate: coordinateForPoint(currentPoint)
    readonly property var trackCoordinates: buildTrackCoordinates()
    readonly property string providerLabel: pluginName.length > 0 ? pluginName.toUpperCase() : "OSM"
    readonly property bool localTileCacheRequested: tileMode === "local_arcgis_cache"
    readonly property bool localTileCacheRegistered: localTileCacheRequested && tileRoot.length > 0
    readonly property bool backdropActive: backdropSource.length > 0 && mapBackdrop.status === Image.Ready
    readonly property string tileFeedLabel: "QtLocation / " + providerLabel + " 实时底图"
    readonly property string tileFeedDetail: localTileCacheRequested
        ? (localTileCacheRegistered
            ? "已登记本地 ArcGIS 缓存目录；当前仍通过 " + providerLabel + " provider 渲染，后续可桥接本地瓦片。"
            : "等待本地 ArcGIS 缓存目录；当前仍通过 " + providerLabel + " provider 渲染。")
        : "当前通过内置 " + providerLabel + " provider 渲染，位置与轨迹直接落在真实地理底图。"
    readonly property string tileFeedState: localTileCacheRequested
        ? (localTileCacheRegistered ? ("本地缓存已登记 / 当前 " + providerLabel + " 在线") : ("本地缓存待登记 / 当前 " + providerLabel + " 在线"))
        : "在线 provider"
    readonly property string stageProjectionLabel: effectiveProjectionLabel()
    readonly property string anchorDetailText: anchorLabel && anchorLabel !== "--"
        ? "锚点 " + anchorLabel
        : "锚点待命"
    readonly property string currentDetailText: currentDetail && currentDetail.length > 0
        ? currentDetail
        : "地图主舞台"
    readonly property string positionText: hasCurrentPoint
        ? (Number(currentPoint["latitude"]).toFixed(4) + "°, " + Number(currentPoint["longitude"]).toFixed(4) + "°")
        : "--"
    readonly property string headingText: shellWindow
        ? shellWindow.formattedMetric(headingDeg, 0, "°")
        : (Math.round(headingDeg) + "°")
    readonly property string trackNodeLabel: trackCoordinates.length > 0
        ? String(trackCoordinates.length) + " 节点"
        : "等待航迹"
    readonly property color mapWaterTop: landingMode ? "#204d67" : "#132a40"
    readonly property color mapWaterBottom: landingMode ? "#0b1622" : "#050d15"
    readonly property color gridGlow: shellWindow ? shellWindow.panelGlowStrong : "#74d7ff"
    readonly property color trackColor: shellWindow ? shellWindow.accentCyan : "#8fe6ff"
    readonly property color emphasisColor: shellWindow ? shellWindow.accentAmber : "#ffbf55"
    readonly property color neutralColor: shellWindow ? shellWindow.accentBlue : "#78b2d4"
    readonly property color warningFill: "#251d10"
    readonly property color onlineFill: "#0b2432"
    readonly property color neutralFill: "#102033"
    readonly property var defaultCenterCoordinate: landingMode
        ? QtPositioning.coordinate(28.0, 103.0)
        : QtPositioning.coordinate(30.572815, 104.066801)
    readonly property var headingConeCoordinates: buildHeadingCone()

    function toneColor(tone) {
        if (shellWindow) {
            if (tone === "warning")
                return shellWindow.accentAmber
            if (tone === "online")
                return shellWindow.accentCyan
            if (tone === "degraded")
                return Qt.lighter(shellWindow.accentAmber, 1.06)
            if (tone === "neutral")
                return shellWindow.accentBlue
            return shellWindow.textSecondary
        }
        if (tone === "warning")
            return "#ffbf55"
        if (tone === "online")
            return "#8fe6ff"
        if (tone === "degraded")
            return "#f7ca72"
        if (tone === "neutral")
            return "#78b2d4"
        return "#88abc5"
    }

    function toneFill(tone) {
        if (tone === "warning" || tone === "degraded")
            return warningFill
        if (tone === "online")
            return onlineFill
        return neutralFill
    }

    function coordinateForPoint(point) {
        var lon = Number(point["longitude"])
        var lat = Number(point["latitude"])
        if (!isFinite(lon) || !isFinite(lat))
            return defaultCenterCoordinate
        return QtPositioning.coordinate(lat, lon)
    }

    function buildTrackCoordinates() {
        var coordinates = []
        if (!trackData)
            return coordinates
        for (var index = 0; index < trackData.length; ++index) {
            var point = trackData[index]
            var lon = Number(point["longitude"])
            var lat = Number(point["latitude"])
            if (isFinite(lon) && isFinite(lat))
                coordinates.push(QtPositioning.coordinate(lat, lon))
        }
        if (coordinates.length === 0 && hasCurrentPoint)
            coordinates.push(currentCoordinate)
        return coordinates
    }

    function buildHeadingCone() {
        if (!hasCurrentPoint)
            return []

        var leftEdge = currentCoordinate.atDistanceAndAzimuth(38000, headingDeg - 18)
        var tip = currentCoordinate.atDistanceAndAzimuth(72000, headingDeg)
        var rightEdge = currentCoordinate.atDistanceAndAzimuth(38000, headingDeg + 18)
        return [currentCoordinate, leftEdge, tip, rightEdge, currentCoordinate]
    }

    function recommendedZoom(spanDegrees) {
        var span = Math.max(0.0, Number(spanDegrees))
        if (span <= 0.015)
            return 13.6
        if (span <= 0.05)
            return 12.4
        if (span <= 0.12)
            return 11.3
        if (span <= 0.35)
            return 10.0
        if (span <= 0.8)
            return 8.8
        if (span <= 2.5)
            return 7.1
        if (span <= 8.0)
            return 5.6
        if (span <= 18.0)
            return 4.2
        return 2.5
    }

    function effectiveProjectionLabel() {
        var label = String(root.projectionLabel || "")
        if (!label || label.indexOf("EQUIRECTANGULAR") >= 0)
            return "WGS84 底图 / QTLOCATION"
        return label + " · WGS84"
    }

    function refreshViewport() {
        if (!geoMap)
            return

        var coordinates = trackCoordinates.slice(0)
        if (hasCurrentPoint)
            coordinates.push(currentCoordinate)

        if (coordinates.length === 0) {
            geoMap.center = defaultCenterCoordinate
            geoMap.zoomLevel = landingMode ? 2.2 : 5.0
            return
        }

        var minLat = 90.0
        var maxLat = -90.0
        var minLon = 180.0
        var maxLon = -180.0

        for (var index = 0; index < coordinates.length; ++index) {
            var coordinate = coordinates[index]
            minLat = Math.min(minLat, coordinate.latitude)
            maxLat = Math.max(maxLat, coordinate.latitude)
            minLon = Math.min(minLon, coordinate.longitude)
            maxLon = Math.max(maxLon, coordinate.longitude)
        }

        var latSpan = Math.max(0.0, maxLat - minLat)
        var lonSpan = Math.max(0.0, maxLon - minLon)
        var span = Math.max(latSpan, lonSpan)
        var zoom = recommendedZoom(span)
        if (landingMode)
            zoom = Math.max(2.0, zoom - 0.4)

        geoMap.center = QtPositioning.coordinate((minLat + maxLat) / 2, (minLon + maxLon) / 2)
        geoMap.zoomLevel = Math.max(geoMap.minimumZoomLevel, Math.min(geoMap.maximumZoomLevel, zoom))
    }

    onTrackDataChanged: if (root.stageActive) Qt.callLater(refreshViewport)
    onCurrentPointChanged: if (root.stageActive) Qt.callLater(refreshViewport)
    onHeadingDegChanged: if (root.stageActive) Qt.callLater(refreshViewport)
    onLandingModeChanged: if (root.stageActive) Qt.callLater(refreshViewport)
    onWidthChanged: if (root.stageActive) viewportTimer.restart()
    onHeightChanged: if (root.stageActive) viewportTimer.restart()
    onStageActiveChanged: if (root.stageActive) Qt.callLater(refreshViewport)
    Component.onCompleted: Qt.callLater(refreshViewport)

    Timer {
        id: viewportTimer
        interval: 80
        repeat: false
        onTriggered: root.refreshViewport()
    }

    Rectangle {
        anchors.fill: parent
        radius: shellWindow ? shellWindow.panelRadius : 24
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.mapWaterTop }
            GradientStop { position: 1.0; color: root.mapWaterBottom }
        }
        border.color: shellWindow ? shellWindow.panelGlowStrong : "#1f5f82"
        border.width: 1
    }

    Rectangle {
        id: mapViewport
        anchors.fill: parent
        anchors.margins: root.mapInset
        radius: shellWindow ? shellWindow.panelRadius - shellWindow.scaled(6) : 18
        color: "#08121a"
        border.color: Qt.rgba(root.gridGlow.r, root.gridGlow.g, root.gridGlow.b, 0.18)
        border.width: 1
        clip: true

        Plugin {
            id: mapPlugin
            name: root.pluginName.length > 0 ? root.pluginName : "osm"
        }

        Map {
            id: geoMap
            anchors.fill: parent
            plugin: mapPlugin
            center: root.defaultCenterCoordinate
            zoomLevel: landingMode ? 2.2 : 5.0
            minimumZoomLevel: 2.0
            maximumZoomLevel: 15.8
            bearing: 0
            tilt: 0
            copyrightsVisible: true
            opacity: landingMode ? (root.backdropActive ? 0.26 : 0.62) : (root.backdropActive ? 0.6 : 0.76)

            MapPolyline {
                visible: root.trackCoordinates.length > 1
                line.width: landingMode ? 8 : 7
                line.color: "#3a040b12"
                path: root.trackCoordinates
            }

            MapPolyline {
                visible: root.trackCoordinates.length > 1
                line.width: landingMode ? 4 : 3
                line.color: root.trackColor
                path: root.trackCoordinates
            }

            MapPolygon {
                visible: root.headingConeCoordinates.length >= 3
                border.width: 1
                border.color: Qt.rgba(root.emphasisColor.r, root.emphasisColor.g, root.emphasisColor.b, 0.7)
                color: Qt.rgba(root.emphasisColor.r, root.emphasisColor.g, root.emphasisColor.b, 0.16)
                path: root.headingConeCoordinates
            }

            MapCircle {
                visible: root.hasCurrentPoint
                center: root.currentCoordinate
                radius: 24000
                border.width: 1
                border.color: Qt.rgba(root.trackColor.r, root.trackColor.g, root.trackColor.b, 0.34)
                color: "transparent"
            }

            MapCircle {
                visible: root.hasCurrentPoint
                center: root.currentCoordinate
                radius: 52000
                border.width: 1
                border.color: Qt.rgba(root.trackColor.r, root.trackColor.g, root.trackColor.b, 0.16)
                color: "transparent"
            }

            Repeater {
                model: root.trackCoordinates

                delegate: MapQuickItem {
                    coordinate: modelData
                    anchorPoint.x: pointDot.width / 2
                    anchorPoint.y: pointDot.height / 2
                    visible: index < root.trackCoordinates.length - 1

                    sourceItem: Rectangle {
                        id: pointDot
                        width: landingMode ? 8 : 7
                        height: width
                        radius: width / 2
                        color: Qt.rgba(root.trackColor.r, root.trackColor.g, root.trackColor.b, 0.88)
                        border.color: "#d8f8ff"
                        border.width: 1
                        opacity: 0.9
                    }
                }
            }

            MapQuickItem {
                visible: root.hasCurrentPoint
                coordinate: root.currentCoordinate
                anchorPoint.x: 23
                anchorPoint.y: 23

                sourceItem: Item {
                    width: 46
                    height: 46

                    Rectangle {
                        anchors.centerIn: parent
                        width: 42
                        height: 42
                        radius: width / 2
                        color: "transparent"
                        border.color: Qt.rgba(root.trackColor.r, root.trackColor.g, root.trackColor.b, 0.24)
                        border.width: 1
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        radius: 4
                        color: root.emphasisColor
                        border.color: "#fff3dd"
                        border.width: 1
                        rotation: 45
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: 7
                        height: 7
                        radius: width / 2
                        color: "#fcfffe"
                        border.color: "#fcfffe"
                    }
                }
            }
        }

        Image {
            id: mapBackdrop
            anchors.fill: parent
            visible: root.backdropActive
            source: root.backdropSource
            fillMode: Image.PreserveAspectCrop
            smooth: true
            asynchronous: true
            mipmap: true
            opacity: root.landingMode ? 0.82 : 0.24
        }

        Rectangle {
            anchors.fill: mapBackdrop
            visible: mapBackdrop.visible
            color: root.landingMode ? "#0d162010" : "#0d18212a"
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: root.landingMode ? "#100d1310" : "#28071118" }
                GradientStop { position: 0.42; color: "#11182322" }
                GradientStop { position: 1.0; color: root.landingMode ? "#120d1310" : "#32071118" }
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: parent.height * 0.28
            gradient: Gradient {
                GradientStop { position: 0.0; color: root.landingMode ? "#120d1310" : "#7805121b" }
                GradientStop { position: 0.48; color: root.landingMode ? "#080d130c" : "#2208121b" }
                GradientStop { position: 1.0; color: "#0008121b" }
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.height * 0.34
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#0008121b" }
                GradientStop { position: 0.42; color: root.landingMode ? "#080d130c" : "#2408121b" }
                GradientStop { position: 1.0; color: root.landingMode ? "#140d1310" : "#7608111b" }
            }
        }

        Canvas {
            anchors.fill: parent
            opacity: 0.22
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.strokeStyle = "rgba(143,230,255,0.14)"
                ctx.lineWidth = 1

                for (var row = 1; row < 5; ++row) {
                    var y = (height / 5) * row
                    ctx.beginPath()
                    ctx.moveTo(0, y)
                    ctx.lineTo(width, y)
                    ctx.stroke()
                }

                for (var column = 1; column < 7; ++column) {
                    var x = (width / 7) * column
                    ctx.beginPath()
                    ctx.moveTo(x, 0)
                    ctx.lineTo(x, height)
                    ctx.stroke()
                }
            }
        }
    }

    InsetPanel {
        id: stageInfoPanel
        x: root.overlayMargin
        y: root.overlayMargin
        width: Math.min(
            parent.width - (root.overlayMargin * 2),
            shellWindow ? shellWindow.scaled(root.compactStage ? 232 : 272) : (root.compactStage ? 232 : 272)
        )
        shellWindow: root.shellWindow
        accentColor: root.neutralColor
        prominent: false
        visible: root.showStageBadge && root.bannerDockedBottom

        Text {
            Layout.fillWidth: true
            text: "底图 / Map Feed"
            color: shellWindow ? shellWindow.accentBlue : "#86bfe1"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            font.letterSpacing: shellWindow ? shellWindow.scaled(1.1) : 1.1
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.stageProjectionLabel + " · " + root.providerLabel
            color: shellWindow ? shellWindow.textStrong : "#f6f1e7"
            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 15
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            font.bold: true
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.tileFeedState + " · " + root.trackNodeLabel + " · " + root.anchorDetailText
            color: shellWindow ? shellWindow.textPrimary : "#dbe2e6"
            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            wrapMode: Text.Wrap
        }
    }

    InsetPanel {
        id: bannerPanel
        x: root.overlayMargin
        y: root.bannerDockedBottom
            ? parent.height - height - root.overlayMargin
            : root.overlayMargin
        width: Math.min(
            root.stackedBanner ? parent.width - (root.overlayMargin * 2) : parent.width * (root.bannerDockedBottom ? 0.48 : 0.52),
            shellWindow
                ? shellWindow.scaled(root.bannerDockedBottom ? (root.landingMode ? 420 : 500) : (root.landingMode ? 460 : 560))
                : (root.bannerDockedBottom ? (root.landingMode ? 420 : 500) : (root.landingMode ? 460 : 560))
        )
        shellWindow: root.shellWindow
        accentColor: root.trackColor
        prominent: !root.landingMode
        minimalChrome: root.landingMode
        showAccentRail: !root.landingMode
        fillColor: shellWindow
            ? Qt.rgba(shellWindow.surfaceGlass.r, shellWindow.surfaceGlass.g, shellWindow.surfaceGlass.b, root.landingMode ? 0.54 : 0.92)
            : "#c0142634"
        visible: root.bannerTitle.length > 0 || root.bannerText.length > 0 || (root.bannerChips && root.bannerChips.length > 0)

        Text {
            Layout.fillWidth: true
            text: root.bannerEyebrow
            color: shellWindow ? shellWindow.accentBlue : "#86bfe1"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            font.letterSpacing: shellWindow ? shellWindow.scaled(1.1) : 1.1
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.bannerTitle
            color: shellWindow ? shellWindow.textStrong : "#f6f1e7"
            font.pixelSize: shellWindow
                ? (root.landingMode ? shellWindow.sectionTitleSize + shellWindow.scaled(1) : shellWindow.sectionTitleSize)
                : 24
            font.family: shellWindow ? shellWindow.displayFamily : "Noto Serif CJK SC"
            font.weight: root.landingMode ? Font.DemiBold : Font.Normal
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.bannerText
            color: shellWindow ? shellWindow.textPrimary : "#dbe2e6"
            font.pixelSize: shellWindow ? (root.landingMode ? shellWindow.bodySize + 1 : shellWindow.bodySize) : 13
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            wrapMode: Text.Wrap
        }

        Flow {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.compactGap : 8
            visible: root.bannerChips && root.bannerChips.length > 0

            Repeater {
                model: root.bannerChips

                delegate: ToneChip {
                    shellWindow: root.shellWindow
                    label: modelData["label"]
                    value: modelData["value"]
                    tone: modelData["tone"]
                }
            }
        }
    }

    InsetPanel {
        x: parent.width - width - root.overlayMargin
        y: root.overlayMargin
        width: Math.min(
            parent.width - (root.overlayMargin * 2),
            shellWindow ? shellWindow.scaled(root.landingMode ? 220 : 260) : (root.landingMode ? 220 : 260)
        )
        shellWindow: root.shellWindow
        accentColor: root.toneColor(root.scenarioTone)
        prominent: root.scenarioTone === "warning"
        visible: root.showScenarioBadge && root.scenarioLabel.length > 0

        Text {
            Layout.fillWidth: true
            text: "策略 / Scenario"
            color: shellWindow ? shellWindow.textMuted : "#7590a2"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            font.letterSpacing: shellWindow ? shellWindow.scaled(1.0) : 1.0
        }

        Text {
            Layout.fillWidth: true
            text: root.scenarioLabel
            color: root.toneColor(root.scenarioTone)
            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 15
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            font.bold: true
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.tileFeedState
            color: shellWindow ? shellWindow.textSecondary : "#aab8c2"
            font.pixelSize: shellWindow ? shellWindow.bodySize : 13
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            wrapMode: Text.Wrap
        }
    }

    InsetPanel {
        x: root.overlayMargin
        y: parent.height - height - root.overlayMargin
        width: Math.min(
            parent.width - (root.overlayMargin * 2),
            shellWindow ? shellWindow.scaled(root.compactStage ? 350 : 430) : (root.compactStage ? 350 : 430)
        )
        shellWindow: root.shellWindow
        accentColor: root.neutralColor
        visible: root.showInfoPanels

        Text {
            Layout.fillWidth: true
            text: "底图 / Map Feed"
            color: shellWindow ? shellWindow.accentBlue : "#86bfe1"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            font.letterSpacing: shellWindow ? shellWindow.scaled(1.0) : 1.0
        }

        Text {
            Layout.fillWidth: true
            text: root.tileFeedLabel + " · " + root.providerLabel
            color: shellWindow ? shellWindow.textStrong : "#f6f1e7"
            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 15
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            font.bold: true
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.tileFeedDetail
            color: shellWindow ? shellWindow.textPrimary : "#dbe2e6"
            font.pixelSize: shellWindow ? shellWindow.bodySize : 13
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            wrapMode: Text.Wrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.compactGap : 8

            Rectangle {
                Layout.preferredWidth: shellWindow ? shellWindow.scaled(116) : 116
                Layout.fillWidth: true
                radius: shellWindow ? shellWindow.edgeRadius : 12
                color: root.toneFill("online")
                border.color: root.toneColor("online")
                border.width: 1
                implicitHeight: fieldColumnOne.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                Column {
                    id: fieldColumnOne
                    anchors.fill: parent
                    anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                    spacing: 2

                    Text {
                        width: parent.width
                        text: "航迹"
                        color: shellWindow ? shellWindow.textMuted : "#7590a2"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    }

                    Text {
                        width: parent.width
                        text: root.trackNodeLabel
                        color: shellWindow ? shellWindow.textStrong : "#f6f1e7"
                        font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                        font.bold: true
                        wrapMode: Text.Wrap
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: shellWindow ? shellWindow.scaled(116) : 116
                Layout.fillWidth: true
                radius: shellWindow ? shellWindow.edgeRadius : 12
                color: root.toneFill("neutral")
                border.color: root.toneColor("neutral")
                border.width: 1
                implicitHeight: fieldColumnTwo.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                Column {
                    id: fieldColumnTwo
                    anchors.fill: parent
                    anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                    spacing: 2

                    Text {
                        width: parent.width
                        text: "锚点"
                        color: shellWindow ? shellWindow.textMuted : "#7590a2"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    }

                    Text {
                        width: parent.width
                        text: root.anchorDetailText
                        color: shellWindow ? shellWindow.textStrong : "#f6f1e7"
                        font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                        font.bold: true
                        wrapMode: Text.Wrap
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.stageProjectionLabel
            color: shellWindow ? shellWindow.textSecondary : "#aab8c2"
            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            wrapMode: Text.Wrap
        }
    }

    InsetPanel {
        x: parent.width - width - root.overlayMargin
        y: parent.height - height - root.overlayMargin
        width: Math.min(
            parent.width - (root.overlayMargin * 2),
            shellWindow ? shellWindow.scaled(root.compactStage ? 240 : 300) : (root.compactStage ? 240 : 300)
        )
        shellWindow: root.shellWindow
        accentColor: root.emphasisColor
        prominent: !root.compactStage
        visible: root.showTelemetryPanel

        Text {
            Layout.fillWidth: true
            text: "飞行读数 / Flight Core"
            color: shellWindow ? shellWindow.accentBlue : "#86bfe1"
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            font.letterSpacing: shellWindow ? shellWindow.scaled(1.0) : 1.0
        }

        Text {
            Layout.fillWidth: true
            text: root.positionText
            color: shellWindow ? shellWindow.textStrong : "#f6f1e7"
            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 15
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            font.bold: true
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: "航向 " + root.headingText + "  ·  " + root.currentDetailText
            color: shellWindow ? shellWindow.textPrimary : "#dbe2e6"
            font.pixelSize: shellWindow ? shellWindow.bodySize : 13
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            text: root.tileMode === "local_arcgis_cache" && root.tileRoot.length > 0
                ? ("缓存目录 " + root.tileRoot)
                : ("提供器 " + root.providerLabel + " · 格式 " + root.tileFormat.toUpperCase())
            color: shellWindow ? shellWindow.textSecondary : "#aab8c2"
            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            wrapMode: Text.WrapAnywhere
        }
    }
}
