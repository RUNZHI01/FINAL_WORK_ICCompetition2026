import QtQuick 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    property var shellWindow: null
    property var trackData: []
    property var currentPoint: ({})
    property real headingDeg: 0
    property string backdropMode: "canvas"
    property string backdropSource: ""
    property string currentLabel: "实时航迹"
    property string currentDetail: ""
    property string anchorLabel: "--"
    property string projectionLabel: "经纬投影 / EQUIRECTANGULAR"
    property string scenarioLabel: ""
    property string scenarioTone: "neutral"
    property bool landingMode: false
    property bool stageActive: true
    property bool preloadAssets: false
    property string chinaGeoJsonSource: Qt.resolvedUrl("../assets/china-official.geojson")
    property string worldGeoJsonSource: Qt.resolvedUrl("../assets/world-countries-ne50m.geojson")
    property var chinaGeoPaths: []
    property var worldGeoPaths: []
    property bool chinaGeoJsonPending: false
    property bool worldGeoJsonPending: false
    property bool chinaScene: false
    readonly property bool chinaTheaterMode: chinaScene
    readonly property bool chinaGeoJsonLoaded: chinaGeoPaths.length > 0
    readonly property bool worldGeoJsonLoaded: worldGeoPaths.length > 0
    readonly property real chinaMinLongitude: 72
    readonly property real chinaMaxLongitude: 136
    readonly property real chinaMinLatitude: 16
    readonly property real chinaMaxLatitude: 56
    property real scanSweepDeg: 0
    property string bannerEyebrow: landingMode ? "全球指挥主舞台" : "实时指挥舞台"
    property string bannerTitle: currentLabel && currentLabel.length > 0
        ? currentLabel
        : (landingMode ? "世界主墙板" : "实时航迹")
    property string bannerText: currentDetailText
    property var bannerChips: []
    property bool showStageBadge: true
    property bool showScenarioBadge: true
    property bool showInfoPanels: true
    property bool preferBottomBannerDock: false

    readonly property int mapInset: shellWindow ? shellWindow.scaled(landingMode ? 10 : 18) : (landingMode ? 10 : 18)
    readonly property int overlayMargin: shellWindow ? shellWindow.scaled(landingMode ? 11 : 16) : (landingMode ? 11 : 16)
    readonly property bool minimalBanner: landingMode && bannerEyebrow.length === 0
    readonly property bool landingMicroBadge: landingMode && minimalBanner
    readonly property int bannerPadding: shellWindow
        ? shellWindow.scaled(minimalBanner ? 8 : (landingMode ? 10 : 11))
        : (minimalBanner ? 8 : (landingMode ? 10 : 11))
    readonly property int bannerGap: shellWindow
        ? shellWindow.scaled(minimalBanner ? 4 : (landingMode ? 6 : 6))
        : (minimalBanner ? 4 : (landingMode ? 6 : 6))
    readonly property int bannerAccentOffset: landingMode
        ? (shellWindow ? shellWindow.scaled(minimalBanner ? 8 : 10) : (minimalBanner ? 8 : 10))
        : 0
    readonly property int badgePadding: shellWindow ? shellWindow.scaled(landingMicroBadge ? 8 : 9) : (landingMicroBadge ? 8 : 9)
    readonly property color oceanTop: landingMode ? "#091826" : "#060e1a"
    readonly property color oceanBottom: landingMode ? "#040a14" : "#020810"
    readonly property color landFill: landingMode ? "#4a7090" : "#3e6585"
    readonly property color landFillBright: landingMode ? "#6a98b8" : "#5888a5"
    readonly property color coastlineColor: shellWindow ? Qt.lighter(shellWindow.accentCyan, 1.04) : "#8fe6ff"
    readonly property color gridMinor: shellWindow ? shellWindow.gridLine : "#123147"
    readonly property color gridMajor: shellWindow ? shellWindow.gridLineStrong : "#245b80"
    readonly property color labelColor: shellWindow ? Qt.lighter(shellWindow.textMuted, 1.2) : "#8fa7bb"
    readonly property color mapGlow: shellWindow ? shellWindow.panelGlowStrong : "#78d8ff"
    readonly property color markerColor: shellWindow ? shellWindow.accentCyan : "#8fe6ff"
    readonly property color emphasisColor: shellWindow ? shellWindow.accentAmber : "#ffbf55"
    readonly property color overlayCardColor: shellWindow
        ? Qt.rgba(shellWindow.surfaceGlass.r, shellWindow.surfaceGlass.g, shellWindow.surfaceGlass.b, landingMode ? 0.42 : 0.78)
        : (landingMode ? "#b3122330" : "#d2142634")
    readonly property color overlayCardColorSoft: shellWindow
        ? Qt.rgba(shellWindow.surfaceQuiet.r, shellWindow.surfaceQuiet.g, shellWindow.surfaceQuiet.b, landingMode ? 0.34 : 0.82)
        : (landingMode ? "#8a09121a" : "#b8091219")
    readonly property color overlayCardColorDeep: shellWindow
        ? Qt.rgba(shellWindow.shellExterior.r, shellWindow.shellExterior.g, shellWindow.shellExterior.b, landingMode ? 0.26 : 0.6)
        : "#8d040b11"
    readonly property bool hasCurrentPoint: isFinite(Number(currentPoint["longitude"])) && isFinite(Number(currentPoint["latitude"]))
    readonly property bool compactStage: width < (landingMode ? 760 : 880)
    readonly property bool useExternalBackdrop: backdropMode === "asset" && backdropSource.length > 0
    readonly property bool externalBackdropActive: useExternalBackdrop && externalBackdropImage.status === Image.Ready
    readonly property real markerX: hasCurrentPoint ? projectX(Number(currentPoint["longitude"])) : width * 0.5
    readonly property real markerY: hasCurrentPoint ? projectY(Number(currentPoint["latitude"])) : height * 0.5
    readonly property bool leftCallout: markerX > width * 0.64
    readonly property bool showCurrentCallout: hasCurrentPoint && !landingMode
    readonly property real plotWidth: Math.max(1, width - (mapInset * 2))
    readonly property real plotHeight: Math.max(1, height - (mapInset * 2))
    readonly property string anchorDetailText: anchorLabel && anchorLabel !== "--"
        ? "锚点 " + anchorLabel
        : "锚点待命"
    readonly property string currentDetailText: currentDetail && currentDetail.length > 0
        ? currentDetail
        : "世界地图主墙板"
    readonly property string infoRailHeadingText: shellWindow
        ? shellWindow.formattedMetric(headingDeg, 0, "°")
        : (Math.round(headingDeg) + "°")
    readonly property string infoRailPositionText: hasCurrentPoint
        ? (Number(currentPoint["latitude"]).toFixed(2) + "°, " + Number(currentPoint["longitude"]).toFixed(2) + "°")
        : "--"
    readonly property string infoRailAnchorText: anchorLabel && anchorLabel.length > 0 && anchorLabel !== "--"
        ? anchorLabel
        : "待命"
    readonly property bool stackedBanner: width < (landingMode ? 620 : 780)
    readonly property bool bannerDockedBottom: preferBottomBannerDock
        && width >= (shellWindow ? shellWindow.scaled(landingMode ? 280 : 340) : (landingMode ? 280 : 340))
    readonly property real bannerMaxWidth: Math.max(
        shellWindow
            ? shellWindow.scaled(
                bannerDockedBottom
                    ? (landingMode ? (minimalBanner ? 320 : 352) : 340)
                    : (landingMode ? 312 : 260)
            )
            : (
                bannerDockedBottom
                    ? (landingMode ? (minimalBanner ? 320 : 352) : 340)
                    : (landingMode ? 312 : 260)
            ),
        Math.min(
            width - (overlayMargin * 2),
            shellWindow
                ? shellWindow.scaled(
                    bannerDockedBottom
                        ? (landingMode ? (minimalBanner ? 430 : 470) : 500)
                        : (landingMode ? 420 : 560)
                )
                : (
                    bannerDockedBottom
                        ? (landingMode ? (minimalBanner ? 430 : 470) : 500)
                        : (landingMode ? 420 : 560)
                )
        )
    )
    readonly property real scenarioPlateMaxWidth: Math.max(
        shellWindow ? shellWindow.scaled(landingMode ? 148 : 176) : (landingMode ? 148 : 176),
        Math.min(
            width * (landingMode ? 0.32 : 0.42),
            shellWindow ? shellWindow.scaled(landingMode ? 210 : 250) : (landingMode ? 210 : 250)
        )
    )
    readonly property int topOverlayHeight: Math.max(
        stageLabelPlate.visible ? stageLabelPlate.height : 0,
        scenarioPlate.visible ? scenarioPlate.height : 0
    )
    readonly property real infoRailMaxWidth: Math.max(
        shellWindow ? shellWindow.scaled(260) : 260,
        Math.min(
            width - (overlayMargin * 2),
            shellWindow ? shellWindow.scaled(390) : 390
        )
    )
    readonly property string trackNodeLabel: trackData && trackData.length > 0
        ? String(trackData.length) + " 节点"
        : "等待航迹"
    readonly property var continentPolygons: [
        [
            [-168, 72], [-156, 67], [-149, 60], [-141, 58], [-132, 52], [-124, 48],
            [-122, 40], [-117, 32], [-110, 24], [-102, 20], [-94, 18], [-86, 19],
            [-80, 24], [-79, 31], [-76, 40], [-71, 46], [-63, 52], [-58, 60],
            [-66, 67], [-82, 72], [-102, 76], [-124, 75], [-146, 74]
        ],
        [
            [-56, 82], [-34, 78], [-24, 72], [-28, 64], [-42, 60], [-56, 62],
            [-64, 70], [-60, 78]
        ],
        [
            [-81, 12], [-74, 7], [-69, 0], [-64, -10], [-61, -22], [-60, -34],
            [-64, -47], [-72, -55], [-78, -52], [-80, -38], [-79, -22], [-77, -8]
        ],
        [
            [-11, 36], [-6, 43], [2, 48], [14, 54], [30, 60], [48, 64], [66, 67],
            [88, 69], [110, 70], [128, 67], [144, 61], [158, 56], [170, 47],
            [170, 40], [160, 33], [149, 27], [136, 21], [124, 23], [112, 18],
            [102, 10], [95, 6], [88, 9], [82, 18], [74, 22], [64, 27], [54, 31],
            [44, 31], [34, 37], [26, 44], [16, 46], [8, 44], [0, 40]
        ],
        [
            [67, 24], [77, 28], [87, 22], [83, 10], [76, 7], [70, 12]
        ],
        [
            [95, 8], [106, 5], [116, 0], [124, -5], [128, 2], [122, 12], [112, 15], [100, 13]
        ],
        [
            [128, 31], [139, 35], [145, 42], [141, 46], [132, 42]
        ],
        [
            [-17, 37], [2, 36], [18, 34], [32, 31], [42, 20], [48, 9], [45, -7],
            [40, -22], [33, -34], [20, -35], [10, -25], [2, -10], [-5, 7], [-10, 22]
        ],
        [
            [112, -11], [132, -10], [152, -18], [154, -30], [146, -39], [132, -42],
            [118, -36], [112, -24]
        ],
        [
            [-180, -70], [-150, -74], [-120, -78], [-90, -80], [-60, -82], [-30, -80],
            [0, -79], [30, -80], [60, -82], [90, -80], [120, -78], [150, -75],
            [180, -72], [180, -86], [-180, -86]
        ]
    ]
    readonly property var continentLabels: [
        { "label": "北美", "lon": -108, "lat": 50 },
        { "label": "南美", "lon": -60, "lat": -18 },
        { "label": "欧洲", "lon": 18, "lat": 52 },
        { "label": "非洲", "lon": 18, "lat": 5 },
        { "label": "亚洲", "lon": 94, "lat": 46 },
        { "label": "大洋洲", "lon": 134, "lat": -25 }
    ]
    readonly property var latitudeTicks: [-60, -30, 0, 30, 60]
    readonly property var longitudeTicks: [-120, -60, 0, 60, 120]
    readonly property var chinaLatitudeTicks: [20, 30, 40, 50]
    readonly property var chinaLongitudeTicks: [80, 100, 120, 130]
    readonly property var chinaLabels: [
        { "label": "新疆", "lon": 85.0, "lat": 42.0 },
        { "label": "成都", "lon": 104.0668, "lat": 30.5728 },
        { "label": "北京", "lon": 116.4074, "lat": 39.9042 },
        { "label": "上海", "lon": 121.4737, "lat": 31.2304 },
        { "label": "深圳", "lon": 114.0579, "lat": 22.5431 }
    ]

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
            return "#5ab7ff"
        return "#88abc5"
    }

    function toneFill(tone) {
        if (shellWindow) {
            if (tone === "warning" || tone === "degraded")
                return "#2a2014"
            if (tone === "online")
                return "#0f2a22"
            if (tone === "neutral")
                return "#122838"
            return "#0c1e30"
        }
        if (tone === "warning" || tone === "degraded")
            return "#2a2014"
        if (tone === "online")
            return "#0f2a22"
        if (tone === "neutral")
            return "#122838"
        return "#0c1e30"
    }

    function projectX(longitude) {
        if (root.chinaTheaterMode) {
            var lon = Number(longitude)
            var lonSpan = Math.max(1, root.chinaMaxLongitude - root.chinaMinLongitude)
            return mapInset + ((lon - root.chinaMinLongitude) / lonSpan) * plotWidth
        }
        return mapInset + ((Number(longitude) + 180) / 360) * plotWidth
    }

    function projectY(latitude) {
        if (root.chinaTheaterMode) {
            var lat = Number(latitude)
            var latSpan = Math.max(1, root.chinaMaxLatitude - root.chinaMinLatitude)
            return mapInset + ((root.chinaMaxLatitude - lat) / latSpan) * plotHeight
        }
        return mapInset + ((90 - Number(latitude)) / 180) * plotHeight
    }

    function requestBasePaint() {
        baseCanvas.requestPaint()
    }

    function requestTrackPaint() {
        trackCanvas.requestPaint()
    }

    function requestSweepPaint() {
        sweepCanvas.requestPaint()
    }

    function requestStagePaint() {
        root.requestBasePaint()
        root.requestTrackPaint()
        root.requestSweepPaint()
    }

    function ensureGeoJsonLoaded() {
        if (!root.visible && !root.preloadAssets && !root.stageActive)
            return
        if (!chinaGeoJsonLoaded && !chinaGeoJsonPending)
            loadChinaGeoJson()
        if (!worldGeoJsonLoaded && !worldGeoJsonPending)
            loadWorldGeoJson()
    }

    function drawPolygon(ctx, polygon, fillColor, strokeColor) {
        if (!polygon || polygon.length < 2)
            return

        ctx.beginPath()
        for (var pointIndex = 0; pointIndex < polygon.length; ++pointIndex) {
            var point = polygon[pointIndex]
            var px = root.projectX(point[0])
            var py = root.projectY(point[1])
            if (pointIndex === 0)
                ctx.moveTo(px, py)
            else
                ctx.lineTo(px, py)
        }
        ctx.closePath()
        ctx.fillStyle = fillColor
        ctx.strokeStyle = strokeColor
        ctx.lineWidth = 1.25
        ctx.fill()
        ctx.stroke()
    }

    function drawPolygonStrokeOnly(ctx, polygon, strokeColor, lineWidth) {
        if (!polygon || polygon.length < 2)
            return
        ctx.beginPath()
        for (var i = 0; i < polygon.length; ++i) {
            var pt = polygon[i]
            var px = root.projectX(pt[0])
            var py = root.projectY(pt[1])
            if (i === 0)
                ctx.moveTo(px, py)
            else
                ctx.lineTo(px, py)
        }
        ctx.closePath()
        ctx.strokeStyle = strokeColor
        ctx.lineWidth = lineWidth
        ctx.stroke()
    }

    function drawTrack(ctx) {
        if (!trackData || trackData.length < 1)
            return

        ctx.save()
        ctx.lineJoin = "round"
        ctx.lineCap = "round"
        if (trackData.length > 1) {
            var shadowWidth = landingMode ? 8.4 : 7.2
            var washWidth = landingMode ? 4.8 : 4.2
            var trackWidth = landingMode ? 3.1 : 2.6
            var segCount = trackData.length - 1

            for (var seg = 0; seg < segCount; ++seg) {
                var segAlpha = 0.15 + 0.85 * (seg / segCount)
                var p0 = trackData[seg]
                var p1 = trackData[seg + 1]
                var sx0 = projectX(p0["longitude"])
                var sy0 = projectY(p0["latitude"])
                var sx1 = projectX(p1["longitude"])
                var sy1 = projectY(p1["latitude"])

                ctx.globalAlpha = segAlpha * 0.78
                ctx.beginPath(); ctx.moveTo(sx0, sy0); ctx.lineTo(sx1, sy1)
                ctx.strokeStyle = "rgb(4,11,18)"; ctx.lineWidth = shadowWidth; ctx.stroke()

                ctx.globalAlpha = segAlpha * 0.18
                ctx.beginPath(); ctx.moveTo(sx0, sy0); ctx.lineTo(sx1, sy1)
                ctx.strokeStyle = "rgb(255,255,255)"; ctx.lineWidth = washWidth; ctx.stroke()

                ctx.globalAlpha = segAlpha * 0.94
                ctx.beginPath(); ctx.moveTo(sx0, sy0); ctx.lineTo(sx1, sy1)
                ctx.strokeStyle = "rgb(143,230,255)"; ctx.lineWidth = trackWidth; ctx.stroke()
            }
            ctx.globalAlpha = 1.0

            ctx.beginPath()
            for (var midIndex = 0; midIndex < trackData.length; ++midIndex) {
                var midPoint = trackData[midIndex]
                var mx = projectX(midPoint["longitude"])
                var my = projectY(midPoint["latitude"])
                var dotAlpha = 0.15 + 0.85 * (midIndex / Math.max(1, trackData.length - 1))
                ctx.globalAlpha = dotAlpha * 0.88
                ctx.beginPath()
                ctx.arc(mx, my, midIndex === trackData.length - 1 ? (landingMode ? 5.2 : 4.6) : (landingMode ? 3.2 : 2.8), 0, Math.PI * 2)
                ctx.fillStyle = "rgb(143,230,255)"
                ctx.fill()
            }
            ctx.globalAlpha = 1.0
        }

        if (hasCurrentPoint) {
            var cx = markerX
            var cy = markerY
            var headingRadians = (headingDeg - 90) * Math.PI / 180

            ctx.beginPath()
            ctx.arc(cx, cy, 22, 0, Math.PI * 2)
            ctx.strokeStyle = "rgba(143,230,255,0.26)"
            ctx.lineWidth = 1.4
            ctx.stroke()

            ctx.beginPath()
            ctx.arc(cx, cy, 56, 0, Math.PI * 2)
            ctx.strokeStyle = "rgba(143,230,255,0.12)"
            ctx.lineWidth = 1.2
            ctx.stroke()

            ctx.beginPath()
            ctx.arc(cx, cy, 38, (-140 * Math.PI) / 180, (40 * Math.PI) / 180)
            ctx.strokeStyle = "rgba(255,191,85,0.34)"
            ctx.lineWidth = 1.2
            ctx.stroke()

            ctx.beginPath()
            ctx.moveTo(cx, cy)
            ctx.lineTo(cx + (Math.cos(headingRadians) * 74), cy + (Math.sin(headingRadians) * 74))
            ctx.strokeStyle = "rgba(255,255,255,0.62)"
            ctx.lineWidth = 1.4
            ctx.stroke()

            ctx.beginPath()
            ctx.arc(cx, cy, 6.5, 0, Math.PI * 2)
            ctx.fillStyle = "rgba(255,255,255,0.92)"
            ctx.fill()
        }
        ctx.restore()
    }

    function flattenGeometryRings(geometry) {
        if (!geometry)
            return []
        var type = geometry.type
        var coords = geometry.coordinates
        if (!coords)
            return []
        var rings = []
        if (type === "Polygon") {
            for (var i = 0; i < coords.length; ++i)
                rings.push(coords[i])
        } else if (type === "MultiPolygon") {
            for (var j = 0; j < coords.length; ++j)
                for (var k = 0; k < coords[j].length; ++k)
                    rings.push(coords[j][k])
        }
        return rings
    }

    function featureTone(index) {
        var tones = [
            "#3858a8",
            "#3050a0",
            "#4060b0",
            "#2848a0",
            "#3454a8"
        ]
        return tones[index % tones.length]
    }

    function loadChinaGeoJson() {
        if (!chinaGeoJsonSource || chinaGeoJsonSource.length === 0 || chinaGeoJsonPending || chinaGeoJsonLoaded)
            return
        chinaGeoJsonPending = true
        var request = new XMLHttpRequest()
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE)
                return
            chinaGeoJsonPending = false
            if (request.status !== 200 && request.status !== 0) {
                baseCanvas.requestPaint()
                return
            }
            try {
                var payload = JSON.parse(request.responseText)
                var features = payload && payload.features ? payload.features : []
                var nextPaths = []
                for (var featureIndex = 0; featureIndex < features.length; ++featureIndex) {
                    var feature = features[featureIndex]
                    var rings = flattenGeometryRings(feature.geometry)
                    for (var ringIndex = 0; ringIndex < rings.length; ++ringIndex) {
                        nextPaths.push({
                            "ring": rings[ringIndex],
                            "name": (feature.properties || {}).NAME || (feature.properties || {}).name || "",
                            "index": nextPaths.length,
                        })
                    }
                }
                chinaGeoPaths = nextPaths
                baseCanvas.requestPaint()
            } catch (error) {
                chinaGeoPaths = []
                baseCanvas.requestPaint()
            }
        }
        request.open("GET", chinaGeoJsonSource)
        request.send()
    }

    function loadWorldGeoJson() {
        if (!worldGeoJsonSource || worldGeoJsonSource.length === 0 || worldGeoJsonPending || worldGeoJsonLoaded)
            return
        worldGeoJsonPending = true
        var request = new XMLHttpRequest()
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE)
                return
            worldGeoJsonPending = false
            if (request.status !== 200 && request.status !== 0) {
                baseCanvas.requestPaint()
                return
            }
            try {
                var payload = JSON.parse(request.responseText)
                var features = payload && payload.features ? payload.features : []
                var nextPaths = []
                for (var featureIndex = 0; featureIndex < features.length; ++featureIndex) {
                    var feature = features[featureIndex]
                    var rings = flattenGeometryRings(feature.geometry)
                    for (var ringIndex = 0; ringIndex < rings.length; ++ringIndex) {
                        nextPaths.push({
                            "ring": rings[ringIndex],
                            "name": (feature.properties || {}).NAME || (feature.properties || {}).name || "",
                            "index": nextPaths.length,
                        })
                    }
                }
                worldGeoPaths = nextPaths
                baseCanvas.requestPaint()
            } catch (error) {
                worldGeoPaths = []
                baseCanvas.requestPaint()
            }
        }
        request.open("GET", worldGeoJsonSource)
        request.send()
    }

    function paintStaticMap(ctx, canvasWidth, canvasHeight) {
        var ocean = ctx.createLinearGradient(0, 0, 0, canvasHeight)
        ocean.addColorStop(0.0, root.oceanTop)
        ocean.addColorStop(0.34, root.landingMode ? "#1a4060" : "#0c1e32")
        ocean.addColorStop(0.62, root.landingMode ? "#0f2840" : "#081626")
        ocean.addColorStop(1.0, root.oceanBottom)
        ctx.fillStyle = ocean
        ctx.fillRect(0, 0, canvasWidth, canvasHeight)

        var beamCenterX = canvasWidth * 0.72
        var beamCenterY = canvasHeight * 0.32
        var beamRadius = Math.max(1, canvasWidth * 0.55)
        var beam = ctx.createRadialGradient(beamCenterX, beamCenterY, 0, beamCenterX, beamCenterY, beamRadius)
        beam.addColorStop(0.0, root.landingMode ? "rgba(120,216,255,0.1)" : "rgba(120,216,255,0.18)")
        beam.addColorStop(0.52, root.landingMode ? "rgba(120,216,255,0.04)" : "rgba(120,216,255,0.07)")
        beam.addColorStop(1.0, "rgba(120,216,255,0.0)")
        ctx.fillStyle = beam
        ctx.fillRect(0, 0, canvasWidth, canvasHeight)

        var hazeCenterX = canvasWidth * 0.22
        var hazeCenterY = canvasHeight * 0.78
        var hazeRadius = Math.max(1, canvasWidth * 0.42)
        var haze = ctx.createRadialGradient(hazeCenterX, hazeCenterY, 0, hazeCenterX, hazeCenterY, hazeRadius)
        haze.addColorStop(0.0, root.landingMode ? "rgba(231,201,142,0.09)" : "rgba(240,185,124,0.12)")
        haze.addColorStop(0.5, root.landingMode ? "rgba(231,201,142,0.03)" : "rgba(240,185,124,0.04)")
        haze.addColorStop(1.0, "rgba(240,185,124,0.0)")
        ctx.fillStyle = haze
        ctx.fillRect(0, 0, canvasWidth, canvasHeight)

        ctx.save()
        ctx.beginPath()
        ctx.rect(root.mapInset, root.mapInset, root.plotWidth, root.plotHeight)
        ctx.clip()

        var latitudeTickSource = root.chinaTheaterMode ? root.chinaLatitudeTicks : root.latitudeTicks
        for (var latitudeIndex = 0; latitudeIndex < latitudeTickSource.length; ++latitudeIndex) {
            var latitude = latitudeTickSource[latitudeIndex]
            var latitudeY = root.projectY(latitude)
            ctx.beginPath()
            ctx.moveTo(root.mapInset, latitudeY)
            ctx.lineTo(width - root.mapInset, latitudeY)
            ctx.strokeStyle = (!root.chinaTheaterMode && latitude === 0)
                ? (root.landingMode ? "rgba(176,221,255,0.38)" : "rgba(132,191,255,0.36)")
                : (root.landingMode ? "rgba(88,122,151,0.22)" : "rgba(68,98,126,0.24)")
            ctx.lineWidth = (!root.chinaTheaterMode && latitude === 0) ? 1.4 : 1.0
            ctx.stroke()
        }

        var longitudeTickSource = root.chinaTheaterMode ? root.chinaLongitudeTicks : root.longitudeTicks
        for (var longitudeIndex = 0; longitudeIndex < longitudeTickSource.length; ++longitudeIndex) {
            var longitude = longitudeTickSource[longitudeIndex]
            var longitudeX = root.projectX(longitude)
            ctx.beginPath()
            ctx.moveTo(longitudeX, root.mapInset)
            ctx.lineTo(longitudeX, height - root.mapInset)
            ctx.strokeStyle = (!root.chinaTheaterMode && longitude === 0)
                ? (root.landingMode ? "rgba(176,221,255,0.38)" : "rgba(132,191,255,0.36)")
                : (root.landingMode ? "rgba(48,76,102,0.26)" : "rgba(31,49,69,0.32)")
            ctx.lineWidth = (!root.chinaTheaterMode && longitude === 0) ? 1.4 : 1.0
            ctx.stroke()
        }

        if (root.chinaTheaterMode && root.chinaGeoJsonLoaded) {
            for (var cpIdx = 0; cpIdx < root.chinaGeoPaths.length; ++cpIdx) {
                var cp = root.chinaGeoPaths[cpIdx]
                drawPolygon(ctx, cp["ring"], root.landFill, Qt.rgba(root.coastlineColor.r, root.coastlineColor.g, root.coastlineColor.b, 0.6))
            }
        } else if (root.worldGeoJsonLoaded) {
            for (var worldPathIndex = 0; worldPathIndex < root.worldGeoPaths.length; ++worldPathIndex) {
                var worldPath = root.worldGeoPaths[worldPathIndex]
                var worldRing = worldPath["ring"]
                ctx.save()
                ctx.translate(0, 2)
                drawPolygon(ctx, worldRing, "rgba(3, 10, 16, 0.22)", "rgba(0,0,0,0)")
                ctx.restore()
                ctx.save()
                ctx.globalAlpha = 0.2
                drawPolygonStrokeOnly(ctx, worldRing, "rgba(100, 140, 255, 0.8)", 4)
                ctx.globalAlpha = 1.0
                ctx.restore()
                drawPolygon(ctx, worldRing, root.featureTone(worldPathIndex), "rgba(100, 140, 255, 0.6)")
            }
        } else if (!root.externalBackdropActive) {
            for (var polygonIndex = 0; polygonIndex < root.continentPolygons.length; ++polygonIndex) {
                var polygon = root.continentPolygons[polygonIndex]
                var shadowPolygon = root.continentPolygons[polygonIndex]
                ctx.save()
                ctx.translate(0, 3)
                drawPolygon(ctx, shadowPolygon, "rgba(5,13,22,0.36)", "rgba(0,0,0,0)")
                ctx.restore()

                var fillColor = polygonIndex % 3 === 0
                    ? root.landFillBright
                    : (polygonIndex % 2 === 0 ? root.landFill : Qt.darker(root.landFill, 1.04))
                drawPolygon(ctx, polygon, fillColor, Qt.rgba(root.coastlineColor.r, root.coastlineColor.g, root.coastlineColor.b, root.landingMode ? 0.62 : 0.5))
            }
        }

        ctx.beginPath()
        ctx.rect(root.mapInset, root.mapInset, root.plotWidth, root.plotHeight)
        ctx.strokeStyle = root.landingMode ? "rgba(188,233,255,0.18)" : "rgba(172,236,255,0.22)"
        ctx.lineWidth = 1
        ctx.stroke()
        ctx.restore()

        var vigGrad = ctx.createRadialGradient(
            canvasWidth * 0.5, canvasHeight * 0.5, Math.min(canvasWidth, canvasHeight) * 0.32,
            canvasWidth * 0.5, canvasHeight * 0.5, Math.max(canvasWidth, canvasHeight) * 0.58
        )
        vigGrad.addColorStop(0.0, "rgba(0,0,0,0)")
        vigGrad.addColorStop(1.0, "rgba(0,0,0,0.18)")
        ctx.fillStyle = vigGrad
        ctx.fillRect(0, 0, canvasWidth, canvasHeight)
    }

    function paintTrackOverlay(ctx, canvasWidth, canvasHeight) {
        if (root.hasCurrentPoint) {
            var spotlightRadius = Math.max(1, Math.min(canvasWidth, canvasHeight) * 0.38)
            var spotlight = ctx.createRadialGradient(root.markerX, root.markerY, 0, root.markerX, root.markerY, spotlightRadius)
            spotlight.addColorStop(0.0, "rgba(255,255,255,0.03)")
            spotlight.addColorStop(0.3, "rgba(172,236,255,0.06)")
            spotlight.addColorStop(1.0, "rgba(172,236,255,0.0)")
            ctx.fillStyle = spotlight
            ctx.fillRect(0, 0, canvasWidth, canvasHeight)
        }

        ctx.save()
        ctx.beginPath()
        ctx.rect(root.mapInset, root.mapInset, root.plotWidth, root.plotHeight)
        ctx.clip()
        root.drawTrack(ctx)
        ctx.restore()
    }

    function paintSweepOverlay(ctx, canvasWidth, canvasHeight) {
        if (!root.hasCurrentPoint)
            return

        var sweepAngle = (root.scanSweepDeg % 360) * Math.PI / 180
        var sweepLength = Math.max(canvasWidth, canvasHeight) * 0.38
        ctx.save()
        ctx.globalCompositeOperation = "lighter"
        ctx.beginPath()
        ctx.moveTo(root.markerX, root.markerY)
        ctx.arc(root.markerX, root.markerY, sweepLength, sweepAngle - 0.28, sweepAngle)
        ctx.closePath()
        var sweepGrad = ctx.createRadialGradient(
            root.markerX, root.markerY, 0,
            root.markerX, root.markerY, sweepLength
        )
        sweepGrad.addColorStop(0.0, "rgba(120,220,255,0.10)")
        sweepGrad.addColorStop(0.4, "rgba(120,220,255,0.04)")
        sweepGrad.addColorStop(1.0, "rgba(120,220,255,0.0)")
        ctx.fillStyle = sweepGrad
        ctx.fill()
        ctx.restore()
    }

    Image {
        id: externalBackdropImage
        anchors.fill: parent
        anchors.margins: root.mapInset
        visible: root.externalBackdropActive
        source: root.useExternalBackdrop ? root.backdropSource : ""
        fillMode: Image.PreserveAspectCrop
        smooth: true
        asynchronous: true
        mipmap: true
        opacity: root.landingMode ? 0.94 : 0.7
        onStatusChanged: root.requestBasePaint()
    }

    Rectangle {
        anchors.fill: externalBackdropImage
        visible: externalBackdropImage.visible
        color: root.landingMode ? "#0c151b08" : "#40101814"
    }

    Canvas {
        id: baseCanvas
        anchors.fill: parent
        antialiasing: true
        renderStrategy: Canvas.Threaded
        renderTarget: Canvas.FramebufferObject

        onPaint: {
            var ctx = getContext("2d")
            var canvasWidth = Math.max(1, root.width)
            var canvasHeight = Math.max(1, root.height)
            ctx.reset()
            ctx.clearRect(0, 0, canvasWidth, canvasHeight)
            root.paintStaticMap(ctx, canvasWidth, canvasHeight)
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    Canvas {
        id: trackCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var canvasWidth = Math.max(1, root.width)
            var canvasHeight = Math.max(1, root.height)
            ctx.reset()
            ctx.clearRect(0, 0, canvasWidth, canvasHeight)
            root.paintTrackOverlay(ctx, canvasWidth, canvasHeight)
        }
    }

    Canvas {
        id: sweepCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var canvasWidth = Math.max(1, root.width)
            var canvasHeight = Math.max(1, root.height)
            ctx.reset()
            ctx.clearRect(0, 0, canvasWidth, canvasHeight)
            root.paintSweepOverlay(ctx, canvasWidth, canvasHeight)
        }
    }

    Timer {
        running: root.stageActive && root.hasCurrentPoint
        repeat: true
        interval: 200
        onTriggered: {
            root.scanSweepDeg += 12
            root.requestSweepPaint()
        }
    }

    onTrackDataChanged: if (root.stageActive) root.requestTrackPaint()
    onCurrentPointChanged: {
        if (root.stageActive) {
            root.requestTrackPaint()
            root.requestSweepPaint()
        }
    }
    onHeadingDegChanged: if (root.stageActive) root.requestTrackPaint()
    onBackdropModeChanged: root.requestBasePaint()
    onBackdropSourceChanged: root.requestBasePaint()
    onWidthChanged: root.requestStagePaint()
    onHeightChanged: root.requestStagePaint()
    onLandingModeChanged: root.requestStagePaint()
    onStageActiveChanged: if (root.stageActive) root.requestStagePaint()
    onChinaSceneChanged: root.requestBasePaint()
    onVisibleChanged: {
        if (visible) {
            ensureGeoJsonLoaded()
            root.requestStagePaint()
        }
    }
    onChinaGeoJsonSourceChanged: {
        chinaGeoPaths = []
        chinaGeoJsonPending = false
        ensureGeoJsonLoaded()
        root.requestBasePaint()
    }
    onWorldGeoJsonSourceChanged: {
        worldGeoPaths = []
        worldGeoJsonPending = false
        ensureGeoJsonLoaded()
        root.requestBasePaint()
    }

    Component.onCompleted: {
        ensureGeoJsonLoaded()
        root.requestStagePaint()
    }

    Repeater {
        model: root.chinaTheaterMode ? root.chinaLabels : (!root.landingMode ? root.continentLabels : [])

        delegate: Text {
            text: modelData["label"]
            color: root.labelColor
            font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            font.weight: Font.DemiBold
            x: root.projectX(modelData["lon"]) - (width / 2)
            y: root.projectY(modelData["lat"]) - (height / 2)
            opacity: 0.94
        }
    }

    Repeater {
        model: root.chinaTheaterMode ? root.chinaLatitudeTicks : (!root.landingMode ? root.latitudeTicks : [])

        delegate: Text {
            text: String(modelData) + "°"
            color: root.labelColor
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            x: root.mapInset + (shellWindow ? shellWindow.scaled(8) : 8)
            y: root.projectY(modelData) - (height / 2)
            opacity: 0.7
        }
    }

    Repeater {
        model: root.chinaTheaterMode ? root.chinaLongitudeTicks : (!root.landingMode ? root.longitudeTicks : [])

        delegate: Text {
            text: (root.chinaTheaterMode ? "" : (modelData > 0 ? "+" : "")) + String(modelData) + "°"
            color: root.labelColor
            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
            x: root.projectX(modelData) - (width / 2)
            y: height - root.mapInset + (shellWindow ? shellWindow.scaled(6) : 6)
            opacity: 0.7
        }
    }

    Rectangle {
        id: stageLabelPlate
        visible: root.showStageBadge
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: root.overlayMargin
        radius: shellWindow ? shellWindow.edgeRadius : 12
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.overlayCardColor }
            GradientStop { position: 1.0; color: root.overlayCardColorSoft }
        }
        border.color: root.landingMode
            ? Qt.rgba(root.mapGlow.r, root.mapGlow.g, root.mapGlow.b, 0.82)
            : root.mapGlow
        border.width: 1
        implicitWidth: stageLabelColumn.implicitWidth + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)
        implicitHeight: stageLabelColumn.implicitHeight + (root.badgePadding * 2)
        clip: true
        opacity: 0

        NumberAnimation on opacity { from: 0; to: 1; duration: 400; easing.type: Easing.OutCubic }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: shellWindow ? shellWindow.scaled(8) : 8
            anchors.rightMargin: shellWindow ? shellWindow.scaled(8) : 8
            height: shellWindow ? shellWindow.scaled(1) : 1
            color: Qt.rgba(root.mapGlow.r, root.mapGlow.g, root.mapGlow.b, root.landingMicroBadge ? 0.42 : 0.62)
            opacity: 0.88
        }

        Column {
            id: stageLabelColumn
            anchors.centerIn: parent
            spacing: shellWindow ? shellWindow.scaled(root.landingMicroBadge ? 1 : 2) : (root.landingMicroBadge ? 1 : 2)

            Text {
                text: root.chinaTheaterMode
                    ? "中国任务区主墙"
                    : (root.landingMicroBadge
                        ? "全球主墙板"
                        : (root.landingMode ? "全球主墙板" : "世界态势地图"))
                color: root.mapGlow
                font.pixelSize: shellWindow ? (root.landingMicroBadge ? shellWindow.captionSize : shellWindow.captionSize + 1) : (root.landingMicroBadge ? 10 : 11)
                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                font.letterSpacing: shellWindow ? shellWindow.scaled(root.landingMicroBadge ? 0.7 : 1) : (root.landingMicroBadge ? 0.7 : 1)
                opacity: root.landingMode ? 0.94 : 1.0
            }

            Text {
                text: root.chinaTheaterMode
                    ? "WGS84 · CHINA THEATER"
                    : (root.externalBackdropActive
                        ? (root.landingMicroBadge ? "WGS84 · LOCAL ASSET" : root.projectionLabel + " / LOCAL ASSET")
                        : (root.landingMicroBadge ? "WGS84 · " + root.trackNodeLabel : root.projectionLabel))
                color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            }

            Text {
                visible: !root.landingMicroBadge
                text: root.trackNodeLabel + "  ·  锚点 " + root.infoRailAnchorText
                color: shellWindow ? shellWindow.textMuted : "#68859d"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            }
        }
    }

    Rectangle {
        id: scenarioPlate
        visible: root.showScenarioBadge
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.overlayMargin
        width: Math.min(implicitWidth, root.scenarioPlateMaxWidth)
        radius: shellWindow ? shellWindow.edgeRadius : 12
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.overlayCardColor }
            GradientStop { position: 1.0; color: root.overlayCardColorSoft }
        }
        border.color: toneColor(scenarioTone)
        border.width: 1
        implicitWidth: scenarioColumn.implicitWidth + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)
        opacity: 0

        NumberAnimation on opacity { from: 0; to: 1; duration: 450; easing.type: Easing.OutCubic }

        Behavior on border.color { ColorAnimation { duration: 200 } }
        implicitHeight: scenarioColumn.implicitHeight + (root.badgePadding * 2)
        clip: true

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: shellWindow ? shellWindow.scaled(8) : 8
            anchors.rightMargin: shellWindow ? shellWindow.scaled(8) : 8
            height: shellWindow ? shellWindow.scaled(1) : 1
            color: Qt.rgba(toneColor(scenarioTone).r, toneColor(scenarioTone).g, toneColor(scenarioTone).b, root.landingMicroBadge ? 0.42 : 0.58)
            opacity: 0.92
        }

        Column {
            id: scenarioColumn
            anchors.fill: parent
            anchors.margins: root.badgePadding
            spacing: shellWindow ? shellWindow.scaled(root.landingMicroBadge ? 1 : 2) : (root.landingMicroBadge ? 1 : 2)

            Text {
                width: parent.width
                text: root.landingMicroBadge
                    ? "推荐策略"
                    : (root.compactStage
                        ? (root.landingMode ? "场景焦点" : "当前关注")
                        : (root.landingMode ? "场景焦点" : "当前关注"))
                color: shellWindow ? shellWindow.textMuted : "#68859d"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? (root.landingMicroBadge ? shellWindow.monoFamily : shellWindow.uiFamily) : (root.landingMicroBadge ? "JetBrains Mono" : "Noto Sans CJK SC")
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                text: scenarioLabel && scenarioLabel.length > 0 ? scenarioLabel : "全球链路稳态"
                color: toneColor(scenarioTone)
                font.pixelSize: shellWindow ? (root.landingMicroBadge ? shellWindow.bodySize + 1 : shellWindow.bodyEmphasisSize) : (root.landingMicroBadge ? 13 : 14)
                font.bold: true
                font.family: shellWindow ? shellWindow.displayFamily : "Noto Sans CJK SC"
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                text: root.landingMicroBadge ? root.anchorDetailText : root.currentDetailText
                color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                elide: Text.ElideRight
            }
        }
    }

    Rectangle {
        id: commandBanner
        visible: root.bannerTitle.length > 0 || root.bannerText.length > 0 || root.bannerChips.length > 0
        width: root.bannerMaxWidth
        x: root.bannerDockedBottom
            ? root.overlayMargin
            : Math.max(root.overlayMargin, (root.width - width) / 2)
        y: root.bannerDockedBottom
            ? root.height - height - root.overlayMargin
            : (root.stackedBanner
                ? root.overlayMargin + root.topOverlayHeight + (shellWindow ? shellWindow.scaled(10) : 10)
                : root.overlayMargin + (shellWindow ? shellWindow.scaled(root.landingMode ? 8 : 6) : (root.landingMode ? 8 : 6)))
        radius: shellWindow ? shellWindow.scaled(root.landingMode ? 14 : 13) : (root.landingMode ? 14 : 13)
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.overlayCardColor }
            GradientStop { position: 0.52; color: root.overlayCardColorSoft }
            GradientStop { position: 1.0; color: root.overlayCardColorDeep }
        }
        border.color: root.landingMode
            ? Qt.rgba(root.mapGlow.r, root.mapGlow.g, root.mapGlow.b, 0.36)
            : Qt.rgba(root.mapGlow.r, root.mapGlow.g, root.mapGlow.b, 0.72)
        border.width: 1
        opacity: 0

        NumberAnimation on opacity { from: 0; to: 1; duration: 500; easing.type: Easing.OutCubic }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            color: "transparent"
            border.color: "#08ffffff"
            border.width: 1
        }

        Rectangle {
            visible: root.landingMode
            width: shellWindow ? shellWindow.scaled(root.minimalBanner ? 2 : 3) : (root.minimalBanner ? 2 : 3)
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.leftMargin: root.bannerPadding
            anchors.topMargin: root.bannerPadding
            anchors.bottomMargin: root.bannerPadding
            radius: width / 2
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.24; color: root.mapGlow }
                GradientStop { position: 0.76; color: Qt.lighter(root.mapGlow, 1.12) }
                GradientStop { position: 1.0; color: "transparent" }
            }
            opacity: 0.64
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: shellWindow ? shellWindow.scaled(2) : 2
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.16; color: root.mapGlow }
                GradientStop { position: 0.54; color: Qt.lighter(root.mapGlow, 1.12) }
                GradientStop { position: 0.84; color: root.mapGlow }
                GradientStop { position: 1.0; color: "transparent" }
            }
            opacity: root.landingMode ? 0.92 : 0.76
        }

        Rectangle {
            width: parent.width * 0.32
            height: parent.height * 0.8
            radius: width / 2
            color: root.mapGlow
            opacity: root.landingMode ? 0.028 : 0.04
            x: -width * 0.16
            y: -height * 0.26
        }

        Rectangle {
            width: parent.width * 0.42
            height: parent.height * 0.92
            radius: width / 2
            color: root.mapGlow
            opacity: root.landingMode ? 0.04 : 0.02
            x: parent.width - (width * 0.72)
            y: -height * 0.22
        }

        Column {
            id: bannerColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: root.bannerPadding + root.bannerAccentOffset
            anchors.rightMargin: root.bannerPadding
            anchors.topMargin: root.bannerPadding
            anchors.bottomMargin: root.bannerPadding
            spacing: root.bannerGap

            Text {
                visible: text.length > 0
                width: parent.width
                text: root.bannerEyebrow
                color: root.mapGlow
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                text: root.bannerTitle
                color: shellWindow ? shellWindow.textStrong : "#f5f9ff"
                font.pixelSize: shellWindow
                    ? shellWindow.bodyEmphasisSize + (root.minimalBanner ? shellWindow.scaled(2) : shellWindow.scaled(3))
                    : (root.minimalBanner ? 16 : 18)
                font.weight: Font.DemiBold
                font.family: shellWindow ? shellWindow.displayFamily : "Noto Sans CJK SC"
                wrapMode: Text.WordWrap
                maximumLineCount: root.landingMode ? 1 : (root.stackedBanner ? 2 : 1)
                elide: Text.ElideRight
            }

            Text {
                visible: text.length > 0
                width: parent.width
                text: root.bannerText
                color: shellWindow ? shellWindow.textSecondary : "#8fa9be"
                font.pixelSize: shellWindow ? shellWindow.captionSize + 2 : 12
                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                wrapMode: Text.WordWrap
                maximumLineCount: root.landingMode ? 1 : (root.stackedBanner ? 2 : 1)
                elide: Text.ElideRight
            }

            Flow {
                visible: root.bannerChips.length > 0
                width: parent.width
                spacing: root.bannerGap

                Repeater {
                    model: root.bannerChips

                    delegate: Rectangle {
                        readonly property var chipData: modelData
                        radius: shellWindow ? shellWindow.edgeRadius : 12
                        color: root.toneFill(String(chipData["tone"] || "neutral"))
                        border.color: root.toneColor(String(chipData["tone"] || "neutral"))
                        border.width: 1
                        implicitWidth: bannerChipColumn.implicitWidth + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                        implicitHeight: bannerChipColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                        Column {
                            id: bannerChipColumn
                            anchors.centerIn: parent
                            spacing: 1

                            Text {
                                text: chipData["label"]
                                color: shellWindow ? shellWindow.textMuted : "#68859d"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }

                            Text {
                                text: chipData["value"]
                                color: shellWindow ? shellWindow.textStrong : "#f5f9ff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
                                font.bold: true
                                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        visible: root.showInfoPanels && width >= (shellWindow ? shellWindow.scaled(520) : 520)
        width: root.infoRailMaxWidth
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.overlayMargin + (shellWindow ? shellWindow.scaled(10) : 10)
        radius: shellWindow ? shellWindow.edgeRadius : 12
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.overlayCardColor }
            GradientStop { position: 0.52; color: root.overlayCardColorSoft }
            GradientStop { position: 1.0; color: root.overlayCardColorDeep }
        }
        border.color: Qt.rgba(root.mapGlow.r, root.mapGlow.g, root.mapGlow.b, root.landingMode ? 0.72 : 0.58)
        border.width: 1
        opacity: 0.96

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            color: "transparent"
            border.color: "#0dffffff"
            border.width: 1
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: shellWindow ? shellWindow.scaled(12) : 12
            anchors.rightMargin: shellWindow ? shellWindow.scaled(12) : 12
            anchors.topMargin: shellWindow ? shellWindow.scaled(8) : 8
            anchors.bottomMargin: shellWindow ? shellWindow.scaled(8) : 8
            spacing: shellWindow ? shellWindow.compactGap : 8

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Text {
                    text: "航迹"
                    color: root.mapGlow
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                    font.letterSpacing: shellWindow ? shellWindow.scaled(0.7) : 0.7
                }

                Text {
                    text: root.trackNodeLabel
                    color: shellWindow ? shellWindow.textStrong : "#f5f9ff"
                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                    font.weight: Font.DemiBold
                    font.family: shellWindow ? shellWindow.displayFamily : "Noto Serif CJK SC"
                }
            }

            Rectangle {
                width: 1
                Layout.fillHeight: true
                color: "#14ffffff"
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Text {
                    text: "锚点"
                    color: root.mapGlow
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                    font.letterSpacing: shellWindow ? shellWindow.scaled(0.7) : 0.7
                }

                Text {
                    text: root.infoRailAnchorText
                    color: shellWindow ? shellWindow.textStrong : "#f5f9ff"
                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                    font.weight: Font.DemiBold
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                width: 1
                Layout.fillHeight: true
                color: "#14ffffff"
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Text {
                    text: "航向 · 定位"
                    color: root.mapGlow
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                    font.letterSpacing: shellWindow ? shellWindow.scaled(0.7) : 0.7
                }

                Text {
                    text: root.infoRailHeadingText + "  ·  " + root.infoRailPositionText
                    color: shellWindow ? shellWindow.textStrong : "#f5f9ff"
                    font.pixelSize: shellWindow ? shellWindow.captionSize + 1 : 11
                    font.weight: Font.DemiBold
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    elide: Text.ElideRight
                }
            }
        }
    }

    Item {
        visible: root.hasCurrentPoint
        x: root.markerX - (width / 2)
        y: root.markerY - (height / 2)
        width: shellWindow ? shellWindow.scaled(38) : 38
        height: width

        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 1.85
            height: width
            radius: width / 2
            color: root.markerColor
            opacity: 0.12

            SequentialAnimation on scale {
                loops: Animation.Infinite
                NumberAnimation { from: 0.78; to: 1.18; duration: 1600 }
                NumberAnimation { from: 1.18; to: 0.78; duration: 1600 }
            }
        }

        Rectangle {
            id: radarPing1
            anchors.centerIn: parent
            width: parent.width * 2.5
            height: width
            radius: width / 2
            color: "transparent"
            border.color: root.markerColor
            border.width: 1.5
            opacity: 0
            scale: 0
            SequentialAnimation on scale {
                loops: Animation.Infinite
                NumberAnimation { from: 0; to: 2.5; duration: 2200; easing.type: Easing.OutQuad }
                PauseAnimation { duration: 200 }
            }
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { from: 0.7; to: 0; duration: 2200; easing.type: Easing.OutQuad }
                PauseAnimation { duration: 200 }
            }
        }

        Rectangle {
            id: radarPing2
            anchors.centerIn: parent
            width: parent.width * 2.5
            height: width
            radius: width / 2
            color: "transparent"
            border.color: root.markerColor
            border.width: 1.2
            opacity: 0
            scale: 0
            SequentialAnimation on scale {
                loops: Animation.Infinite
                PauseAnimation { duration: 1100 }
                NumberAnimation { from: 0; to: 2.5; duration: 2200; easing.type: Easing.OutQuad }
            }
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                PauseAnimation { duration: 1100 }
                NumberAnimation { from: 0.5; to: 0; duration: 2200; easing.type: Easing.OutQuad }
            }
        }

        Item {
            anchors.fill: parent
            rotation: root.headingDeg
            transformOrigin: Item.Center

            Rectangle {
                width: parent.width * 0.16
                height: parent.height * 0.8
                radius: width / 2
                color: root.markerColor
                border.color: "#ffffff"
                border.width: 1
                anchors.centerIn: parent
            }

            Rectangle {
                width: parent.width * 0.82
                height: parent.height * 0.14
                radius: height / 2
                color: root.markerColor
                border.color: "#ffffff"
                border.width: 1
                anchors.centerIn: parent
            }

            Rectangle {
                width: parent.width * 0.26
                height: parent.height * 0.2
                rotation: 45
                radius: height / 2
                color: root.emphasisColor
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: shellWindow ? shellWindow.scaled(1) : 1
            }
        }
    }

    Rectangle {
        visible: root.showCurrentCallout && root.showInfoPanels
        readonly property real preferredY: Math.max(
            shellWindow ? shellWindow.scaled(68) : 68,
            Math.min(
                root.height - implicitHeight - (shellWindow ? shellWindow.scaled(24) : 24),
                root.markerY - (implicitHeight / 2)
            )
        )
        x: root.leftCallout
            ? Math.max(shellWindow ? shellWindow.scaled(16) : 16, root.markerX - width - (shellWindow ? shellWindow.scaled(22) : 22))
            : Math.min(root.width - width - (shellWindow ? shellWindow.scaled(16) : 16), root.markerX + (shellWindow ? shellWindow.scaled(22) : 22))
        y: preferredY
        radius: shellWindow ? shellWindow.edgeRadius : 12
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.overlayCardColor }
            GradientStop { position: 1.0; color: root.overlayCardColorSoft }
        }
        border.color: root.markerColor
        border.width: 1
        implicitWidth: currentCalloutColumn.implicitWidth + ((shellWindow ? shellWindow.scaled(16) : 16) * 2)
        implicitHeight: currentCalloutColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)

        Rectangle {
            y: (parent.height / 2) - 1
            x: root.leftCallout ? parent.width : -((shellWindow ? shellWindow.scaled(18) : 18))
            width: shellWindow ? shellWindow.scaled(18) : 18
            height: 2
            color: root.markerColor
            opacity: 0.8
        }

        Column {
            id: currentCalloutColumn
            anchors.centerIn: parent
            spacing: shellWindow ? shellWindow.scaled(2) : 2

            Text {
                text: root.currentLabel
                color: root.markerColor
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
            }

            Text {
                text: root.currentDetailText
                color: shellWindow ? shellWindow.textStrong : "#f1f7ff"
                font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                font.bold: true
                font.family: shellWindow ? shellWindow.displayFamily : "Noto Sans CJK SC"
            }

            Text {
                text: root.anchorDetailText
                color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
            }
        }
    }
}
