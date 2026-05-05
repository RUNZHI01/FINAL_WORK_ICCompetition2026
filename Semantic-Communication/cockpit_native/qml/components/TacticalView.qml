import QtQuick 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

PanelFrame {
    id: root

    property var panelData: ({})

    readonly property var panel: DataUtils.objectOrEmpty(panelData)
    readonly property var positionData: DataUtils.objectOrEmpty(panel["position"])
    readonly property var kinematicsData: DataUtils.objectOrEmpty(panel["kinematics"])
    readonly property var fixData: DataUtils.objectOrEmpty(panel["fix"])
    readonly property var trackData: DataUtils.arrayOrEmpty(panel["track"])
    readonly property var controlSummary: DataUtils.objectOrEmpty(panel["control_summary"])
    readonly property var feedContractData: DataUtils.objectOrEmpty(panel["feed_contract"])
    readonly property var sampleData: DataUtils.objectOrEmpty(panel["sample"])
    readonly property var shellRightPanelData: shellWindow ? DataUtils.objectOrEmpty(shellWindow.rightPanelData) : ({})
    readonly property var liveAnchorData: DataUtils.objectOrEmpty(shellRightPanelData["live_anchor"])
    readonly property var weakNetworkScenarios: DataUtils.arrayOrEmpty(shellRightPanelData["scenarios"])

    panelColor: shellWindow ? shellWindow.panelColorRaised : "#0d2034"
    borderTone: shellWindow ? shellWindow.borderStrong : "#5fbfff"
    accentTone: shellWindow ? shellWindow.accentCyan : "#8fe6ff"

    readonly property bool compactLayout: shellWindow ? shellWindow.compactLayout : width < 920
    readonly property bool wideLayout: shellWindow ? shellWindow.wideLayout : width >= 1280
    readonly property bool shortViewport: shellWindow ? shellWindow.shortViewport : height < 760
    readonly property int padding: shellWindow ? shellWindow.scaled(compactLayout ? 18 : 22) : 22
    readonly property int gap: shellWindow ? shellWindow.scaled(compactLayout ? 10 : 14) : 14
    readonly property int smallGap: shellWindow ? shellWindow.scaled(8) : 8
    readonly property real headingDeg: Number(kinematicsData["heading_deg"] || 0)
    readonly property var currentPoint: trackPoint(Math.max(trackData.length - 1, 0))
    readonly property var recommendedScenario: recommendedScenarioData()
    readonly property string recommendedScenarioId: shellWindow ? String(shellWindow.recommendedScenarioId || "--") : "--"
    readonly property string recommendedScenarioTone: String(recommendedScenario["tone"] || "neutral")
    readonly property string liveAnchorTone: String(liveAnchorData["tone"] || "neutral")
    readonly property string primaryTone: liveAnchorTone !== "neutral" ? liveAnchorTone : (hasTrack() ? "online" : "neutral")
    readonly property string sourceStatusText: sourceStatusLabel()
    readonly property string sourceText: sourceLabel()
    readonly property string sampleTimestamp: String(sampleData["captured_at"] || "采样时间未知")
    readonly property string coordinateText: coordinateLabel(currentPoint["latitude"], "lat") + " / "
        + coordinateLabel(currentPoint["longitude"], "lon")
    readonly property string trackAgeText: Number(currentPoint["age_sec"] || 0).toFixed(0) + " s"
    readonly property string altitudeLabel: Number(kinematicsData["altitude_m"] || 0).toFixed(0) + " m"
    readonly property string speedLabel: Number(kinematicsData["ground_speed_kph"] || 0).toFixed(0) + " km/h"
    readonly property string headingLabel: headingDeg.toFixed(1) + "°"
    readonly property string fixLabel: String(fixData["type"] || "--") + " / ±" + Number(fixData["confidence_m"] || 0).toFixed(1) + "m"
    readonly property string mapStatusLabel: hasTrack() ? "实时轨迹锁定" : "合同镜像待命"
    readonly property string mapStatusDetail: hasTrack()
        ? "世界主舞台已锁定真实航迹，当前位置直接落在全球底图上。"
        : "当前没有更长的历史航迹，主舞台仍保持合同镜像底图与当前位置。"
    readonly property string aircraftIdText: String(panel["aircraft_id"] || "FT-AIR-01")
    readonly property string missionText: String(panel["mission_call_sign"] || "M9-DEMO")
    readonly property string anchorValue: String(liveAnchorData["valid_instance"] || "--")
    readonly property string anchorDetail: String(liveAnchorData["board_status"] || "板端状态未知")
    readonly property string recommendedSummary: compactMessage(
        String(recommendedScenario["summary"] || recommendedScenario["label"] || "当前主舞台没有额外弱网建议。"),
        "当前主舞台没有额外弱网建议。",
        compactLayout ? 36 : 56
    )
    readonly property var headerChipModel: [
        {
            "label": "链路",
            "value": String(controlSummary["link_profile"] || "--"),
            "tone": "neutral"
        },
        {
            "label": "板端",
            "value": anchorValue,
            "tone": liveAnchorTone
        }
    ]
    readonly property var stageBannerChipModel: [
        {
            "label": "源",
            "value": sourceText,
            "tone": "online"
        },
        {
            "label": "链路",
            "value": String(controlSummary["link_profile"] || "--"),
            "tone": "neutral"
        },
        {
            "label": "航迹",
            "value": String(trackData.length) + " 节点",
            "tone": hasTrack() ? "online" : "neutral"
        }
    ]
    readonly property var railMetricModel: [
        {
            "label": "高度层",
            "value": altitudeLabel,
            "detail": "飞行高度",
            "tone": "online"
        },
        {
            "label": "地速",
            "value": speedLabel,
            "detail": "Ground Speed",
            "tone": "neutral"
        },
        {
            "label": "航向",
            "value": headingLabel,
            "detail": "Heading",
            "tone": "warning"
        },
        {
            "label": "定位",
            "value": fixLabel,
            "detail": "Fix Quality",
            "tone": "neutral"
        }
    ]
    readonly property var bottomMetricModel: [
        {
            "label": "当前位置",
            "value": coordinateText,
            "detail": aircraftIdText,
            "tone": "online"
        },
        {
            "label": "航迹链",
            "value": String(trackData.length) + " 节点 / " + trackAgeText,
            "detail": mapStatusLabel,
            "tone": hasTrack() ? "online" : "neutral"
        },
        {
            "label": "板端锚点",
            "value": anchorValue,
            "detail": compactMessage(anchorDetail, "板端状态未知", compactLayout ? 28 : 44),
            "tone": liveAnchorTone
        },
        {
            "label": "推荐弱网",
            "value": recommendedScenarioId,
            "detail": recommendedSummary,
            "tone": recommendedScenarioTone
        }
    ]
    readonly property color mapOverlayColor: "#de0a1320"
    readonly property color mapOverlayColorSoft: "#bc09111b"
    readonly property int mapRailWidth: shellWindow ? shellWindow.scaled(compactLayout ? 156 : 176) : 176

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
        if (tone === "warning")
            return "#24190a"
        if (tone === "online")
            return "#0b2230"
        if (tone === "degraded")
            return "#1f180b"
        if (tone === "neutral")
            return "#0a1b2a"
        return "#091522"
    }

    function compactMessage(text, fallback, limit) {
        var resolved = String(text || fallback || "")
        var maxLength = Math.max(6, Number(limit || 28))
        if (resolved.length <= maxLength)
            return resolved
        return resolved.slice(0, maxLength - 1) + "…"
    }

    function trackPoint(index) {
        if (trackData.length > 0) {
            var safeIndex = Math.max(0, Math.min(trackData.length - 1, Number(index || 0)))
            return DataUtils.objectOrEmpty(trackData[safeIndex])
        }
        return {
            "longitude": Number(positionData["longitude"] || 0),
            "latitude": Number(positionData["latitude"] || 0),
            "age_sec": 0
        }
    }

    function hasTrack() {
        return trackData.length > 1
    }

    function coordinateLabel(value, axis) {
        var numeric = Number(value || 0)
        var suffix = axis === "lat"
            ? (numeric >= 0 ? "N" : "S")
            : (numeric >= 0 ? "E" : "W")
        return Math.abs(numeric).toFixed(4) + "°" + suffix
    }

    function sourceLabel() {
        return String(feedContractData["active_source_label"] || panel["source_label"] || "--")
    }

    function sourceStatusLabel() {
        return String(panel["source_status"] || feedContractData["active_source_kind"] || "--")
    }

    function recommendedScenarioData() {
        for (var index = 0; index < weakNetworkScenarios.length; ++index) {
            var scenario = DataUtils.objectOrEmpty(weakNetworkScenarios[index])
            if (scenario["recommended"] || String(scenario["scenario_id"] || "") === recommendedScenarioId)
                return scenario
        }
        return weakNetworkScenarios.length > 0 ? DataUtils.objectOrEmpty(weakNetworkScenarios[0]) : ({})
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: root.gap

        ColumnLayout {
            Layout.fillWidth: true
            spacing: root.smallGap

            RowLayout {
                Layout.fillWidth: true
                spacing: root.gap

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.scaled(2) : 2

                    Text {
                        text: "中心主舞台 / COMMAND MAP"
                        color: shellWindow ? shellWindow.accentBlue : "#5ab7ff"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "全球态势地图"
                        color: shellWindow ? shellWindow.textStrong : "#f1f7ff"
                        font.pixelSize: shellWindow ? shellWindow.sectionTitleSize + (compactLayout ? 1 : 4) : 28
                        font.weight: Font.DemiBold
                        font.family: shellWindow ? shellWindow.displayFamily : "Ubuntu Sans"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: missionText + " · " + aircraftIdText + " · " + String(controlSummary["link_profile"] || "--")
                        color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                        font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                        font.family: shellWindow ? shellWindow.uiFamily : "Ubuntu Sans"
                        wrapMode: Text.WordWrap
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignTop
                    radius: shellWindow ? shellWindow.edgeRadius : 12
                    color: toneFill(primaryTone)
                    border.color: toneColor(primaryTone)
                    border.width: 1
                    implicitWidth: statusStampColumn.implicitWidth + ((shellWindow ? shellWindow.scaled(14) : 14) * 2)
                    implicitHeight: statusStampColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)

                    Column {
                        id: statusStampColumn
                        anchors.centerIn: parent
                        spacing: shellWindow ? shellWindow.scaled(2) : 2

                        Text {
                            text: "WORLD MAP STATUS"
                            color: shellWindow ? shellWindow.textMuted : "#68859d"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                        }

                        Text {
                            text: mapStatusLabel
                            color: toneColor(primaryTone)
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                            font.bold: true
                            font.family: shellWindow ? shellWindow.displayFamily : "Ubuntu Sans"
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: mapStatusDetail + " 数据源：" + sourceText + " / " + sourceStatusText + "。"
                color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                font.family: shellWindow ? shellWindow.uiFamily : "Ubuntu Sans"
                wrapMode: Text.WordWrap
            }

            Item {
                Layout.fillWidth: true
                implicitHeight: headerChipFlow.implicitHeight

                Flow {
                    id: headerChipFlow
                    width: parent.width
                    spacing: root.smallGap

                    Repeater {
                        model: root.headerChipModel

                        delegate: Rectangle {
                            readonly property var chipData: modelData
                            property bool chipHov: chipHovArea.containsMouse
                            radius: shellWindow ? shellWindow.edgeRadius : 12
                            color: root.toneFill(chipData["tone"])
                            border.color: root.toneColor(chipData["tone"])
                            border.width: 1
                            scale: chipHov ? 1.02 : 1.0
                            height: headerChipColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                            width: compactLayout
                                ? Math.max((headerChipFlow.width - headerChipFlow.spacing) / 2, shellWindow ? shellWindow.scaled(140) : 140)
                                : (shellWindow ? shellWindow.scaled(172) : 172)

                            Behavior on scale { NumberAnimation { duration: 120 } }

                            MouseArea {
                                id: chipHovArea
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.NoButton
                            }

                            Column {
                                id: headerChipColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
                                anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
                                spacing: 1

                                Text {
                                    width: parent.width
                                    text: chipData["label"]
                                    color: shellWindow ? shellWindow.textMuted : "#68859d"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                    font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    text: chipData["value"]
                                    color: shellWindow ? shellWindow.textStrong : "#f1f7ff"
                                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                                    font.bold: true
                                    font.family: shellWindow ? shellWindow.uiFamily : "Ubuntu Sans"
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: shellWindow ? shellWindow.scaled(compactLayout ? 360 : 460) : 460
            radius: shellWindow ? shellWindow.cardRadius : 16
            clip: true
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#132a41" }
                GradientStop { position: 0.28; color: "#0d1b2a" }
                GradientStop { position: 1.0; color: "#071019" }
            }
            border.color: shellWindow ? shellWindow.borderStrong : "#2d6e99"
            border.width: 1

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: shellWindow ? shellWindow.scaled(3) : 3
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.2; color: shellWindow ? shellWindow.accentBlue : "#5ab7ff" }
                    GradientStop { position: 0.5; color: shellWindow ? shellWindow.accentCyan : "#8fe6ff" }
                    GradientStop { position: 0.8; color: shellWindow ? shellWindow.accentBlue : "#5ab7ff" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: 0.82
            }

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: parent.radius - 1
                color: "transparent"
                border.color: "#123652"
                border.width: 1
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: parent.height * 0.18
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#5c07111b" }
                    GradientStop { position: 0.5; color: "#2407111b" }
                    GradientStop { position: 1.0; color: "#0007111b" }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.height * 0.22
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#0007111b" }
                    GradientStop { position: 0.45; color: "#2407111b" }
                    GradientStop { position: 1.0; color: "#70061018" }
                }
            }

            WorldMapStage {
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.scaled(2) : 2
                shellWindow: root.shellWindow
                trackData: root.trackData
                currentPoint: root.currentPoint
                headingDeg: root.headingDeg
                currentLabel: root.missionText + " 实时航迹"
                currentDetail: root.coordinateText + " · " + root.speedLabel
                anchorLabel: root.anchorValue
                projectionLabel: root.hasTrack() ? "实时航迹投影 / LIVE TRACK FUSION" : "合同镜像投影 / CONTRACT MIRROR"
                scenarioLabel: root.recommendedScenarioId !== "--"
                    ? root.recommendedScenarioId
                    : String(root.controlSummary["link_profile"] || "全球链路稳态")
                scenarioTone: root.recommendedScenarioTone
                bannerEyebrow: "CENTER STAGE / COMMAND MAP"
                bannerTitle: root.missionText + " · " + root.aircraftIdText
                bannerText: root.coordinateText + " · " + root.speedLabel + " · " + root.sourceText + " / " + root.sourceStatusText
                bannerChips: root.stageBannerChipModel
                showStageBadge: true
                showScenarioBadge: false
                showInfoPanels: false
                preferBottomBannerDock: true
            }

            Rectangle {
                visible: !compactLayout
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: shellWindow ? shellWindow.scaled(18) : 18
                radius: shellWindow ? shellWindow.edgeRadius : 12
                gradient: Gradient {
                    GradientStop { position: 0.0; color: root.mapOverlayColor }
                    GradientStop { position: 1.0; color: root.mapOverlayColorSoft }
                }
                border.color: shellWindow ? shellWindow.panelGlowStrong : "#235c82"
                border.width: 1
                width: root.mapRailWidth
                implicitHeight: railMetricColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)

                Column {
                    id: railMetricColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: shellWindow ? shellWindow.scaled(12) : 12
                    anchors.rightMargin: shellWindow ? shellWindow.scaled(12) : 12
                    anchors.topMargin: shellWindow ? shellWindow.scaled(12) : 12
                    spacing: shellWindow ? shellWindow.scaled(8) : 8

                    Text {
                        text: "飞行读数 / Flight Core"
                        color: shellWindow ? shellWindow.accentBlue : "#5ab7ff"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                    }

                    Repeater {
                        model: root.railMetricModel

                        delegate: Rectangle {
                            readonly property var metricData: modelData
                            property bool railHov: railHovArea.containsMouse
                            width: parent.width
                            radius: shellWindow ? shellWindow.edgeRadius : 12
                            color: root.toneFill(metricData["tone"])
                            border.color: Qt.rgba(root.toneColor(metricData["tone"]).r, root.toneColor(metricData["tone"]).g, root.toneColor(metricData["tone"]).b, railHov ? 1.0 : 0.7)
                            border.width: 1
                            implicitHeight: railEntryColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                            opacity: 0
                            scale: railHov ? 1.02 : 1.0

                            Behavior on scale { NumberAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Component.onCompleted: railEntranceAnim.start()
                            SequentialAnimation {
                                id: railEntranceAnim
                                PauseAnimation { duration: index * 80 }
                                NumberAnimation { target: parent; property: "opacity"; from: 0; to: 1; duration: 260; easing.type: Easing.OutCubic }
                            }

                            MouseArea {
                                id: railHovArea
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.NoButton
                            }

                            Column {
                                id: railEntryColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
                                anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
                                anchors.topMargin: shellWindow ? shellWindow.scaled(8) : 8
                                spacing: 1

                                Text {
                                    width: parent.width
                                    text: metricData["label"]
                                    color: shellWindow ? shellWindow.textMuted : "#68859d"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                    font.family: shellWindow ? shellWindow.uiFamily : "Ubuntu Sans"
                                }

                                Text {
                                    width: parent.width
                                    text: metricData["value"]
                                    color: shellWindow ? shellWindow.textStrong : "#f1f7ff"
                                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                                    font.bold: true
                                    font.family: shellWindow ? shellWindow.displayFamily : "Ubuntu Sans"
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    text: metricData["detail"]
                                    color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                    font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: shellWindow ? shellWindow.scaled(18) : 18
                width: Math.min(
                    parent.width - ((shellWindow ? shellWindow.scaled(36) : 36) * 2),
                    shellWindow ? shellWindow.scaled(compactLayout ? 300 : 360) : 360
                )
                radius: shellWindow ? shellWindow.edgeRadius : 12
                gradient: Gradient {
                    GradientStop { position: 0.0; color: root.mapOverlayColor }
                    GradientStop { position: 1.0; color: root.mapOverlayColorSoft }
                }
                border.color: root.toneColor(root.recommendedScenarioTone)
                border.width: 1
                implicitHeight: recommendationColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
                    anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
                    height: 2
                    radius: 1
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.3; color: Qt.rgba(root.toneColor(root.recommendedScenarioTone).r, root.toneColor(root.recommendedScenarioTone).g, root.toneColor(root.recommendedScenarioTone).b, 0.4) }
                        GradientStop { position: 0.7; color: Qt.rgba(root.toneColor(root.recommendedScenarioTone).r, root.toneColor(root.recommendedScenarioTone).g, root.toneColor(root.recommendedScenarioTone).b, 0.2) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }

                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.5; to: 1.0; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 1.0; to: 0.5; duration: 1400; easing.type: Easing.InOutSine }
                    }
                }

                Column {
                    id: recommendationColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: shellWindow ? shellWindow.scaled(12) : 12
                    anchors.rightMargin: shellWindow ? shellWindow.scaled(12) : 12
                    anchors.topMargin: shellWindow ? shellWindow.scaled(12) : 12
                    spacing: shellWindow ? shellWindow.scaled(2) : 2

                    Text {
                        text: "主舞台焦点"
                        color: shellWindow ? shellWindow.accentBlue : "#5ab7ff"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                    }

                    Text {
                        text: recommendedScenarioId !== "--"
                            ? ("推荐弱网 " + recommendedScenarioId)
                            : ("数据源 " + sourceText)
                        color: root.toneColor(root.recommendedScenarioTone)
                        font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                        font.bold: true
                        font.family: shellWindow ? shellWindow.displayFamily : "Ubuntu Sans"
                    }

                    Text {
                        width: parent.width
                        text: recommendedSummary + " 采样：" + sampleTimestamp
                        color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                        font.family: shellWindow ? shellWindow.uiFamily : "Ubuntu Sans"
                        wrapMode: Text.WordWrap
                        maximumLineCount: compactLayout ? 2 : 1
                        elide: Text.ElideRight
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: compactLayout ? 2 : 4
            columnSpacing: root.gap
            rowSpacing: root.gap

            Repeater {
                model: root.bottomMetricModel

                delegate: Rectangle {
                    readonly property var metricData: modelData
                    property bool btmHov: btmHovArea.containsMouse
                    Layout.fillWidth: true
                    radius: shellWindow ? shellWindow.edgeRadius : 12
                    color: root.toneFill(metricData["tone"])
                    border.color: Qt.rgba(root.toneColor(metricData["tone"]).r, root.toneColor(metricData["tone"]).g, root.toneColor(metricData["tone"]).b, btmHov ? 1.0 : 0.7)
                    border.width: 1
                    implicitHeight: bottomMetricColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                    opacity: 0
                    scale: btmHov ? 1.015 : 1.0

                    Behavior on scale { NumberAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    Component.onCompleted: btmEntranceAnim.start()
                    SequentialAnimation {
                        id: btmEntranceAnim
                        PauseAnimation { duration: index * 70 }
                        NumberAnimation { target: parent; property: "opacity"; from: 0; to: 1; duration: 280; easing.type: Easing.OutCubic }
                    }

                    MouseArea {
                        id: btmHovArea
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }

                    Column {
                        id: bottomMetricColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.leftMargin: shellWindow ? shellWindow.scaled(10) : 10
                        anchors.rightMargin: shellWindow ? shellWindow.scaled(10) : 10
                        anchors.topMargin: shellWindow ? shellWindow.scaled(10) : 10
                        spacing: shellWindow ? shellWindow.scaled(2) : 2

                        Text {
                            width: parent.width
                            text: metricData["label"]
                            color: shellWindow ? shellWindow.textMuted : "#68859d"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.monoFamily : "Ubuntu Sans Mono"
                            font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                        }

                        Text {
                            width: parent.width
                            text: metricData["value"]
                            color: shellWindow ? shellWindow.textStrong : "#f1f7ff"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                            font.bold: true
                            font.family: shellWindow ? shellWindow.displayFamily : "Ubuntu Sans"
                            wrapMode: Text.WrapAnywhere
                        }

                        Text {
                            width: parent.width
                            text: metricData["detail"]
                            color: shellWindow ? shellWindow.textSecondary : "#88abc5"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.uiFamily : "Ubuntu Sans"
                            wrapMode: Text.WordWrap
                            maximumLineCount: compactLayout ? 2 : 3
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }
}
