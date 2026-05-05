import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

PanelFrame {
    id: root
    property var panelData: ({})
    readonly property var panel: DataUtils.objectOrEmpty(panelData)
    readonly property var liveAnchor: DataUtils.objectOrEmpty(panel["live_anchor"])
    readonly property var scenarios: DataUtils.arrayOrEmpty(panel["scenarios"])
    readonly property bool hasScenarios: scenarios.length > 0
    readonly property string heroStampLabel: String(scenarios.length) + " SCENARIOS"
    readonly property var centerStagePanel: shellWindow ? DataUtils.objectOrEmpty(shellWindow.centerPanelData) : ({})
    readonly property var centerStageControl: shellWindow ? DataUtils.objectOrEmpty(shellWindow.centerControlSummary) : ({})
    readonly property var shellMeta: shellWindow ? DataUtils.objectOrEmpty(shellWindow.meta) : ({})
    readonly property var standbyModel: [
        {
            "label": "推荐档",
            "value": String(panel["recommended_scenario_id"] || "--"),
            "detail": "继续沿用弱网镜像档位"
        },
        {
            "label": "实时锚点",
            "value": String(liveAnchor["board_status"] || "--"),
            "detail": String(liveAnchor["valid_instance"] || "等待在线实例")
        },
        {
            "label": "对照池",
            "value": "0 scenarios",
            "detail": "归档剧本尚未回填到右舷轨"
        }
    ]
    readonly property string stageEscalationLabel: String(liveAnchor["tone"] || "neutral") === "warning"
        ? "右舷弱网轨已经接管风险升级"
        : "右舷弱网轨维持策略伴飞"
    readonly property string stageEscalationDetail: String(liveAnchor["tone"] || "neutral") === "warning"
        ? "把推荐剧本、在线锚点与执行坞站门控汇成同一条风险升级走廊，右舷不再只是单列对照卡片。"
        : "把推荐档位、实时锚点与中心主舞台保持同节奏联动，让右舷轨更像整壳的一段联动 rail。"
    readonly property var stageEscalationModel: [
        {
            "label": "主舞台",
            "value": String(centerStagePanel["mission_call_sign"] || "--"),
            "detail": String(centerStageControl["link_profile"] || "GLOBAL WALLBOARD"),
            "tone": String(liveAnchor["tone"] || "neutral")
        },
        {
            "label": "推荐档",
            "value": String(panel["recommended_scenario_id"] || "--"),
            "detail": String(liveAnchor["valid_instance"] || "等待锚点"),
            "tone": "warning"
        },
        {
            "label": "锚点",
            "value": String(liveAnchor["board_status"] || "--"),
            "detail": String(liveAnchor["probe_summary"] || "--"),
            "tone": String(liveAnchor["tone"] || "neutral")
        },
        {
            "label": "执行",
            "value": shellWindow ? String(shellWindow.enabledBottomActions) + " LIVE" : "--",
            "detail": shellWindow ? (String(shellWindow.bottomActions.length) + " CONTRACTS / " + String(shellMeta["layout_strategy"] || "--")) : "--",
            "tone": shellWindow && shellWindow.enabledBottomActions > 0 ? "online" : "warning"
        }
    ]

    panelColor: shellWindow ? shellWindow.panelColorRaised : "#0a1728"
    borderTone: shellWindow ? shellWindow.panelTraceStrong : "#1a3f61"
    accentTone: shellWindow ? shellWindow.accentCyan : "#72f3ff"

    implicitHeight: contentLayout.implicitHeight + ((shellWindow ? shellWindow.panelPadding : 18) * 2)

    function toneColor(tone) {
        if (shellWindow)
            return shellWindow.toneColor(tone)
        if (tone === "online")
            return "#42f0bc"
        if (tone === "warning" || tone === "degraded")
            return "#ffbf52"
        return "#38b6ff"
    }

    function toneFill(tone) {
        if (tone === "online")
            return "#0c2b29"
        if (tone === "warning" || tone === "degraded")
            return "#302311"
        return "#0d2234"
    }

    function throughputText(scenario) {
        var resolvedScenario = DataUtils.objectOrEmpty(scenario)
        var comparison = DataUtils.objectOrEmpty(resolvedScenario["comparison"])
        return Number(comparison["pipeline_images_per_sec"] || 0).toFixed(3) + " img/s"
    }

    function upliftText(scenario) {
        var resolvedScenario = DataUtils.objectOrEmpty(scenario)
        var comparison = DataUtils.objectOrEmpty(resolvedScenario["comparison"])
        return Number(comparison["throughput_uplift_pct"] || 0).toFixed(3) + "%"
    }

    function savedSecondsText(scenario) {
        var resolvedScenario = DataUtils.objectOrEmpty(scenario)
        var comparison = DataUtils.objectOrEmpty(resolvedScenario["comparison"])
        return Number(comparison["saved_seconds_per_batch"] || 0).toFixed(3) + " s"
    }

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        anchors.margins: shellWindow ? shellWindow.panelPadding : 18
        spacing: shellWindow ? shellWindow.zoneGap : 12

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.cardRadius : 14
            gradient: Gradient {
                GradientStop { position: 0.0; color: shellWindow ? shellWindow.shellDockTop : "#123553" }
                GradientStop { position: 0.5; color: shellWindow ? shellWindow.shellDockMid : "#0a1d30" }
                GradientStop { position: 1.0; color: shellWindow ? shellWindow.shellDockBottom : "#06101a" }
            }
            border.color: shellWindow ? shellWindow.panelGlowStrong : "#3191cf"
            border.width: 1
            implicitHeight: heroColumn.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 14) * 2)

            Rectangle {
                width: parent.width * 0.42
                height: parent.height * 0.88
                radius: width / 2
                color: "#46bbff"
                opacity: 0.1
                x: -width * 0.22
                y: -height * 0.2
            }

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: parent.radius - 1
                color: "transparent"
                border.color: "#13344f"
                border.width: 1
                opacity: 0.8
            }

            Column {
                id: heroColumn
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.cardPadding : 14
                spacing: shellWindow ? shellWindow.compactGap : 8

                RowLayout {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Text {
                        Layout.fillWidth: true
                        text: panel["title"] || "右舷弱网轨 / Right Weak-Link Rail"
                        color: shellWindow ? shellWindow.accentBlue : "#38b6ff"
                        font.pixelSize: shellWindow ? shellWindow.eyebrowSize : 10
                        font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                    }

                    Rectangle {
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: "#091726"
                        border.color: "#1d547c"
                        border.width: 1
                        implicitWidth: heroStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                        implicitHeight: heroStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                        SequentialAnimation on border.color {
                            loops: Animation.Infinite
                            ColorAnimation { from: "#1d547c"; to: "#3a90c8"; duration: 1200; easing.type: Easing.InOutSine }
                            ColorAnimation { from: "#3a90c8"; to: "#1d547c"; duration: 1200; easing.type: Easing.InOutSine }
                        }

                        Text {
                            id: heroStamp
                            anchors.centerIn: parent
                            text: root.heroStampLabel
                            color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        }
                    }
                }

                Text {
                    text: "右舷弱网轨"
                    color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                    font.pixelSize: shellWindow ? shellWindow.sectionTitleSize : 24
                    font.bold: true
                    font.family: shellWindow ? shellWindow.displayFamily : "Noto Sans CJK SC"
                }

                Text {
                    text: "RIGHT WEAK-LINK RAIL / PLAYBOOK"
                    color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                    font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                }

                Text {
                    width: parent.width
                    text: panel["summary"] || ""
                    color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                    font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    width: parent.width
                    radius: shellWindow ? shellWindow.edgeRadius : 10
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#0b1a2a" }
                        GradientStop { position: 1.0; color: "#091321" }
                    }
                    border.color: root.toneColor(liveAnchor["tone"])
                    border.width: 1
                    implicitHeight: watchPostureColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                    Column {
                        id: watchPostureColumn
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                        spacing: 2

                        Text {
                            text: "WATCH POSTURE / LIVE + PLAYBOOK"
                            color: shellWindow ? shellWindow.accentCyan : "#72f3ff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        }

                        Text {
                            width: parent.width
                            text: String(panel["recommended_scenario_id"] || "--") + " / " + String(liveAnchor["valid_instance"] || "--")
                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.bold: true
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            wrapMode: Text.WrapAnywhere
                        }

                        Text {
                            width: parent.width
                            text: String(liveAnchor["board_status"] || liveAnchor["probe_summary"] || "保持归档对照与在线锚点同屏。")
                            color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: "#18405f"
                    opacity: 0.86
                }

                Flow {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: [
                            {
                                "label": "推荐档",
                                "value": String(panel["recommended_scenario_id"] || "--"),
                                "tone": "warning"
                            },
                            {
                                "label": "锚点",
                                "value": String(liveAnchor["valid_instance"] || "--"),
                                "tone": String(liveAnchor["tone"] || "online")
                            },
                            {
                                "label": "板端",
                                "value": String(liveAnchor["board_status"] || "--"),
                                "tone": String(liveAnchor["tone"] || "online")
                            }
                        ]

                        delegate: Rectangle {
                            readonly property var chip: modelData
                            radius: shellWindow ? shellWindow.edgeRadius : 10
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Qt.lighter(root.toneFill(chip["tone"]), 1.14) }
                                GradientStop { position: 1.0; color: root.toneFill(chip["tone"]) }
                            }
                            border.color: root.toneColor(chip["tone"])
                            border.width: 1
                            height: chipColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                            width: Math.max(shellWindow ? shellWindow.scaled(154) : 154, chipColumn.implicitWidth + (shellWindow ? shellWindow.scaled(22) : 22))

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                height: shellWindow ? shellWindow.scaled(2) : 2
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: "transparent" }
                                    GradientStop { position: 0.28; color: root.toneColor(chip["tone"]) }
                                    GradientStop { position: 0.72; color: Qt.lighter(root.toneColor(chip["tone"]), 1.16) }
                                    GradientStop { position: 1.0; color: "transparent" }
                                }
                                opacity: 0.74
                            }

                            Column {
                                id: chipColumn
                                anchors.centerIn: parent
                                spacing: 2

                                Text {
                                    text: chip["label"]
                                    color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                }

                                Text {
                                    text: chip["value"]
                                    color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                    font.bold: true
                                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                    wrapMode: Text.WrapAnywhere
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    radius: shellWindow ? shellWindow.edgeRadius : 10
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#10253a" }
                        GradientStop { position: 0.52; color: "#0b1828" }
                        GradientStop { position: 1.0; color: "#081321" }
                    }
                    border.color: root.toneColor(liveAnchor["tone"])
                    border.width: 1
                    implicitHeight: stageEscalationColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: parent.radius - 1
                        color: "transparent"
                        border.color: "#13344f"
                        border.width: 1
                        opacity: 0.8
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: shellWindow ? shellWindow.scaled(3) : 3
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "transparent" }
                            GradientStop { position: 0.22; color: root.toneColor(liveAnchor["tone"]) }
                            GradientStop { position: 0.72; color: Qt.lighter(root.toneColor(liveAnchor["tone"]), 1.16) }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                        opacity: 0.78
                    }

                    ColumnLayout {
                        id: stageEscalationColumn
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        RowLayout {
                            width: parent.width
                            spacing: shellWindow ? shellWindow.compactGap : 8

                            Text {
                                Layout.fillWidth: true
                                text: "联动走廊 / STAGE ESCALATION BUS"
                                color: shellWindow ? shellWindow.accentCyan : "#72f3ff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                            }

                            Rectangle {
                                radius: shellWindow ? shellWindow.edgeRadius : 10
                                color: "#091726"
                                border.color: "#1d547c"
                                border.width: 1
                                implicitWidth: escalationStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                                implicitHeight: escalationStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                                Text {
                                    id: escalationStamp
                                    anchors.centerIn: parent
                                    text: "RIGHT -> CENTER -> DOCK"
                                    color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            text: root.stageEscalationLabel
                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                            font.bold: true
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            width: parent.width
                            text: root.stageEscalationDetail
                            color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            wrapMode: Text.WordWrap
                        }

                        GridLayout {
                            width: parent.width
                            columns: shellWindow && shellWindow.compactLayout ? 1 : 2
                            columnSpacing: shellWindow ? shellWindow.compactGap : 8
                            rowSpacing: shellWindow ? shellWindow.compactGap : 8

                            Repeater {
                                model: root.stageEscalationModel.length

                                delegate: Rectangle {
                                    readonly property var escalationData: root.stageEscalationModel[index]
                                    Layout.fillWidth: true
                                    radius: shellWindow ? shellWindow.edgeRadius : 10
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: Qt.lighter(root.toneFill(escalationData["tone"]), 1.14) }
                                        GradientStop { position: 1.0; color: root.toneFill(escalationData["tone"]) }
                                    }
                                    border.color: root.toneColor(escalationData["tone"])
                                    border.width: 1
                                    implicitHeight: escalationMetricColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                                    Column {
                                        id: escalationMetricColumn
                                        anchors.fill: parent
                                        anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                                        spacing: 2

                                        Text {
                                            text: escalationData["label"]
                                            color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                        }

                                        Text {
                                            width: parent.width
                                            text: escalationData["value"]
                                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                            font.bold: true
                                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                            wrapMode: Text.WrapAnywhere
                                        }

                                        Text {
                                            width: parent.width
                                            text: escalationData["detail"]
                                            color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
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

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.cardRadius : 14
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#10253a" }
                GradientStop { position: 1.0; color: "#091321" }
            }
            border.color: root.toneColor(liveAnchor["tone"])
            border.width: 1
            implicitHeight: anchorColumn.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 12) * 2)

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: parent.radius - 1
                color: "transparent"
                border.color: "#13334d"
                border.width: 1
                opacity: 0.8
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: shellWindow ? shellWindow.scaled(3) : 3
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.22; color: root.toneColor(liveAnchor["tone"]) }
                    GradientStop { position: 0.72; color: Qt.lighter(root.toneColor(liveAnchor["tone"]), 1.16) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: 0.78
            }

            Column {
                id: anchorColumn
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.cardPadding : 12
                spacing: shellWindow ? shellWindow.scaled(5) : 5

                Text {
                    text: "实时锚点 / Live Anchor"
                    color: shellWindow ? shellWindow.accentCyan : "#72f3ff"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                }

                Text {
                    width: parent.width
                    text: String(liveAnchor["label"] || "") + " / " + String(liveAnchor["board_status"] || "")
                    color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                    font.bold: true
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    wrapMode: Text.WordWrap
                }

                Text {
                    width: parent.width
                    text: String(liveAnchor["probe_summary"] || "")
                    color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Rectangle {
                        Layout.fillWidth: true
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: "#091726"
                        border.color: "#1d547c"
                        border.width: 1
                        implicitHeight: currentAnchorColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(7) : 7) * 2)

                        Column {
                            id: currentAnchorColumn
                            anchors.centerIn: parent
                            spacing: 1

                            Text {
                                text: "当前 / CURRENT"
                                color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }

                            Text {
                                text: String(liveAnchor["current_completed"] || "--")
                                color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: "#091726"
                        border.color: "#1d547c"
                        border.width: 1
                        implicitHeight: baselineAnchorColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(7) : 7) * 2)

                        Column {
                            id: baselineAnchorColumn
                            anchors.centerIn: parent
                            spacing: 1

                            Text {
                                text: "基线 / BASELINE"
                                color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }

                            Text {
                                text: String(liveAnchor["baseline_completed"] || "--")
                                color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.compactGap : 8

            Text {
                text: "策略栈 / PLAYBOOK STACK"
                color: shellWindow ? shellWindow.accentBlue : "#38b6ff"
                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: "#18405f"
                opacity: 0.92
            }

            Rectangle {
                radius: shellWindow ? shellWindow.edgeRadius : 10
                color: "#081625"
                border.color: "#20577f"
                border.width: 1
                implicitWidth: scenarioCountText.implicitWidth + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)
                implicitHeight: scenarioCountText.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                Text {
                    id: scenarioCountText
                    anchors.centerIn: parent
                    text: String(scenarios.length) + " SCENARIOS"
                    color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                }
            }
        }

        ScrollView {
            id: scenariosView
            visible: root.hasScenarios
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Column {
                width: Math.max(0, scenariosView.width - (shellWindow ? shellWindow.scaled(6) : 6))
                spacing: shellWindow ? shellWindow.compactGap : 8

                Repeater {
                    model: scenarios

                    delegate: Rectangle {
                        readonly property var scenario: modelData
                        readonly property bool highlighted: String(scenario["scenario_id"] || "") === String(panel["recommended_scenario_id"] || "")
                        property bool cardHovered: false
                        width: parent.width
                        radius: shellWindow ? shellWindow.cardRadius : 12
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: cardHovered ? (highlighted ? "#1a4060" : "#122a3c") : (highlighted ? "#12304a" : "#0c1a27") }
                            GradientStop { position: 1.0; color: cardHovered ? (highlighted ? "#102030" : "#0e1c28") : (highlighted ? "#0a1622" : "#09131d") }
                        }
                        border.width: 1
                        border.color: cardHovered ? Qt.lighter(highlighted ? "#3aaeff" : root.toneColor(scenario["tone"]), 1.2) : (highlighted ? "#3aaeff" : root.toneColor(scenario["tone"]))
                        implicitHeight: cardColumn.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 12) * 2)
                        scale: cardHovered ? 1.012 : 1.0

                        Behavior on scale { NumberAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.NoButton
                            onEntered: parent.cardHovered = true
                            onExited: parent.cardHovered = false
                        }

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 1
                            radius: parent.radius - 1
                            color: "transparent"
                            border.color: highlighted ? "#1e5b86" : "#112f49"
                            border.width: 1
                            opacity: 0.78
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            height: shellWindow ? shellWindow.scaled(3) : 3
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: "transparent" }
                                GradientStop { position: 0.22; color: highlighted ? "#3aaeff" : root.toneColor(scenario["tone"]) }
                                GradientStop { position: 0.72; color: highlighted ? "#9ff1ff" : Qt.lighter(root.toneColor(scenario["tone"]), 1.16) }
                                GradientStop { position: 1.0; color: "transparent" }
                            }
                            opacity: 0.78
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                            width: shellWindow ? shellWindow.scaled(4) : 4
                            radius: width / 2
                            color: highlighted ? "#72f3ff" : root.toneColor(scenario["tone"])
                            opacity: 0.92
                        }

                        Column {
                            id: cardColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: shellWindow ? shellWindow.cardPadding : 12
                            spacing: shellWindow ? shellWindow.compactGap : 6

                            RowLayout {
                                width: parent.width
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Text {
                                    Layout.fillWidth: true
                                    text: scenario["label"] || ""
                                    color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                    font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                                    font.bold: true
                                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                    wrapMode: Text.WordWrap
                                }

                                Rectangle {
                                    radius: height / 2
                                    color: scenario["recommended"] ? "#173f30" : "#1d2a36"
                                    border.color: scenario["recommended"] ? "#42f0bc" : root.toneColor(scenario["tone"])
                                    border.width: 1
                                    implicitWidth: badgeText.implicitWidth + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)
                                    implicitHeight: badgeText.implicitHeight + ((shellWindow ? shellWindow.scaled(6) : 6) * 2)

                                    SequentialAnimation on opacity {
                                        running: !!scenario["recommended"]
                                        loops: Animation.Infinite
                                        NumberAnimation { from: 1.0; to: 0.6; duration: 1200; easing.type: Easing.InOutSine }
                                        NumberAnimation { from: 0.6; to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                                    }

                                    Text {
                                        id: badgeText
                                        anchors.centerIn: parent
                                        text: scenario["recommended"] ? "推荐" : "对照"
                                        color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                    }
                                }

                                Rectangle {
                                    radius: shellWindow ? shellWindow.edgeRadius : 10
                                    color: "#091726"
                                    border.color: "#1d547c"
                                    border.width: 1
                                    implicitWidth: scenarioIdText.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                                    implicitHeight: scenarioIdText.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                                    Text {
                                        id: scenarioIdText
                                        anchors.centerIn: parent
                                        text: scenario["scenario_id"] || "--"
                                        color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                        font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                    }
                                }
                            }

                            Text {
                                width: parent.width
                                text: scenario["summary"] || ""
                                color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                                wrapMode: Text.WordWrap
                                font.pixelSize: shellWindow ? shellWindow.bodySize : 12
                                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            }

                            Flow {
                                width: parent.width
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: [
                                        {
                                            "label": "SNR",
                                            "value": Number(((scenario["channel"] || {})["snr_db"] || 0)).toFixed(1) + " dB"
                                        },
                                        {
                                            "label": "吞吐",
                                            "value": root.throughputText(scenario)
                                        },
                                        {
                                            "label": "提升",
                                            "value": root.upliftText(scenario)
                                        },
                                        {
                                            "label": "节省",
                                            "value": root.savedSecondsText(scenario)
                                        }
                                    ]

                                    delegate: Rectangle {
                                        readonly property var chip: modelData
                                        radius: shellWindow ? shellWindow.edgeRadius : 10
                                        color: "#091a28"
                                        border.color: "#1f557c"
                                        border.width: 1
                                        height: statColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                                        width: Math.max(shellWindow ? shellWindow.scaled(108) : 108, statColumn.implicitWidth + (shellWindow ? shellWindow.scaled(18) : 18))

                                        Column {
                                            id: statColumn
                                            anchors.centerIn: parent
                                            spacing: 2

                                            Text {
                                                text: chip["label"]
                                                color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                            }

                                            Text {
                                                text: chip["value"]
                                                color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                                font.bold: true
                                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                            }
                                        }
                                    }
                                }
                            }

                            Flow {
                                width: parent.width
                                spacing: shellWindow ? shellWindow.compactGap : 8

                                Repeater {
                                    model: scenario["stage_timings"] || []

                                    delegate: Rectangle {
                                        readonly property var stage: modelData
                                        radius: shellWindow ? shellWindow.edgeRadius : 10
                                        color: "#081422"
                                        border.color: root.toneColor(stage["tone"])
                                        border.width: 1
                                        height: stageColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                                        width: Math.max(shellWindow ? shellWindow.scaled(120) : 120, stageColumn.implicitWidth + (shellWindow ? shellWindow.scaled(20) : 20))

                                        Column {
                                            id: stageColumn
                                            anchors.centerIn: parent
                                            spacing: 2

                                            Text {
                                                text: stage["label"] || ""
                                                color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                            }

                                            Text {
                                                text: Number(stage["mean_ms"] || 0).toFixed(3) + " ms"
                                                color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                                font.bold: true
                                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                width: parent.width
                                text: scenario["operator_note"] || ""
                                color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                                wrapMode: Text.WordWrap
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            visible: !root.hasScenarios
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: shellWindow ? shellWindow.scaled(244) : 244
            radius: shellWindow ? shellWindow.cardRadius : 12
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#0d2033" }
                GradientStop { position: 1.0; color: "#081321" }
            }
            border.color: "#245b84"
            border.width: 1

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: parent.radius - 1
                color: "transparent"
                border.color: "#12324d"
                border.width: 1
                opacity: 0.82
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: shellWindow ? shellWindow.scaled(3) : 3
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.24; color: shellWindow ? shellWindow.accentBlue : "#38b6ff" }
                    GradientStop { position: 0.72; color: shellWindow ? shellWindow.accentCyan : "#72f3ff" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: 0.76
            }

            Column {
                id: standbyColumn
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.cardPadding : 12
                spacing: shellWindow ? shellWindow.compactGap : 8

                RowLayout {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "PLAYBOOK STANDBY / 空剧本待机"
                            color: shellWindow ? shellWindow.accentBlue : "#38b6ff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                        }

                        Text {
                            text: "右舷弱网轨等待剧本对照回填"
                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                            font.bold: true
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                        }

                        Text {
                            width: parent.width
                            text: "当前继续显示推荐档位与在线锚点事实，不伪造不存在的弱网实验结果；一旦剧本接入，这个待机层会被真实对照卡片替换。"
                            color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            wrapMode: Text.WordWrap
                        }
                    }

                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: "#091726"
                        border.color: "#1d547c"
                        border.width: 1
                        implicitWidth: standbyStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)
                        implicitHeight: standbyStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(6) : 6) * 2)

                        Text {
                            id: standbyStamp
                            anchors.centerIn: parent
                            text: "MIRROR ONLY"
                            color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        }
                    }
                }

                Flow {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Repeater {
                        model: root.standbyModel

                        delegate: Rectangle {
                            readonly property var chip: modelData
                            radius: shellWindow ? shellWindow.edgeRadius : 10
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: "#102436" }
                                GradientStop { position: 1.0; color: "#091522" }
                            }
                            border.color: "#245b84"
                            border.width: 1
                            height: standbyChipColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)
                            width: Math.max(shellWindow ? shellWindow.scaled(172) : 172, standbyChipColumn.implicitWidth + (shellWindow ? shellWindow.scaled(22) : 22))

                            Column {
                                id: standbyChipColumn
                                anchors.centerIn: parent
                                spacing: 2

                                Text {
                                    text: chip["label"]
                                    color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                }

                                Text {
                                    text: chip["value"]
                                    color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                    font.bold: true
                                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                }

                                Text {
                                    text: chip["detail"]
                                    color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: shellWindow ? shellWindow.edgeRadius : 10
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#0b1b2d" }
                GradientStop { position: 1.0; color: "#091421" }
            }
            border.color: "#1f557c"
            border.width: 1
            implicitHeight: truthColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: parent.radius - 1
                color: "transparent"
                border.color: "#12324d"
                border.width: 1
                opacity: 0.82
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: shellWindow ? shellWindow.scaled(3) : 3
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.22; color: shellWindow ? shellWindow.accentBlue : "#38b6ff" }
                    GradientStop { position: 0.72; color: shellWindow ? shellWindow.accentCyan : "#72f3ff" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: 0.76
            }

            Column {
                id: truthColumn
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                spacing: shellWindow ? shellWindow.scaled(3) : 3

                RowLayout {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Text {
                        text: "真实性边界 / PLAYBOOK BOUNDARY"
                        color: shellWindow ? shellWindow.accentBlue : "#38b6ff"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                        font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Rectangle {
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: "#091726"
                        border.color: "#1d547c"
                        border.width: 1
                        implicitWidth: truthStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                        implicitHeight: truthStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                        Text {
                            id: truthStamp
                            anchors.centerIn: parent
                            text: panel["recommended_scenario_id"] || "NO PLAYBOOK"
                            color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        }
                    }
                }

                Text {
                    id: truthText
                    width: parent.width
                    text: panel["truth_note"] || ""
                    color: shellWindow ? shellWindow.textMuted : "#4e7392"
                    wrapMode: Text.WordWrap
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    visible: text.length > 0
                }
            }
        }
    }
}
