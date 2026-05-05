import QtQuick 2.15
import QtQuick.Layouts 1.15
import "DataUtils.js" as DataUtils

PanelFrame {
    id: root
    property var panelData: ({})
    readonly property var panel: DataUtils.objectOrEmpty(panelData)

    panelColor: shellWindow ? shellWindow.panelColorRaised : "#091422"
    borderTone: shellWindow ? shellWindow.panelTraceStrong : "#1a3f61"
    accentTone: shellWindow ? shellWindow.accentBlue : "#38b6ff"

    readonly property var rows: DataUtils.arrayOrEmpty(panel["rows"])
    readonly property bool hasRows: rows.length > 0
    readonly property bool dualColumn: width >= (shellWindow ? shellWindow.scaled(520) : 520)
    readonly property string heroStampLabel: String(rows.length) + " ROWS"
    readonly property var centerStagePanel: shellWindow ? DataUtils.objectOrEmpty(shellWindow.centerPanelData) : ({})
    readonly property var centerStageControl: shellWindow ? DataUtils.objectOrEmpty(shellWindow.centerControlSummary) : ({})
    readonly property var shellMeta: shellWindow ? DataUtils.objectOrEmpty(shellWindow.meta) : ({})
    readonly property var standbyModel: [
        {
            "label": "会话总线",
            "value": rowValue("会话") || "等待会话回填",
            "detail": "镜像总线保持在线"
        },
        {
            "label": "板端事件",
            "value": rowValue("最近事件") || "暂无板端事件",
            "detail": "等待现场遥测写入"
        },
        {
            "label": "心跳",
            "value": rowValue("心跳") || "采样心跳待接入",
            "detail": "软件渲染与合同镜像继续可用"
        }
    ]
    readonly property string railBridgeLabel: rowTone("链路档位") === "warning"
        ? "左舷系统轨进入风险回注态"
        : "左舷系统轨维持稳态回注态"
    readonly property string railBridgeDetail: rowTone("链路档位") === "warning"
        ? "把板端链路档位、心跳与最近事件直接回注中心墙板，演示时左舷不再像单独的状态列表。"
        : "把会话、心跳与链路档位持续喂给中心墙板，让左舷系统轨更像总控壳体中的真实供给轨。"
    readonly property var railBridgeModel: [
        {
            "label": "主舞台",
            "value": String(centerStagePanel["mission_call_sign"] || "--"),
            "detail": String(centerStageControl["link_profile"] || "GLOBAL WALLBOARD"),
            "tone": rowTone("链路档位")
        },
        {
            "label": "链路",
            "value": rowValue("链路档位") || "--",
            "detail": rowValue("心跳") || "BOARD HEARTBEAT",
            "tone": rowTone("链路档位")
        },
        {
            "label": "事件",
            "value": rowValue("最近事件") || "--",
            "detail": rowValue("快照原因") || rowValue("事件时间") || "镜像总线",
            "tone": rowTone("最近事件")
        },
        {
            "label": "布局",
            "value": String(shellMeta["layout_strategy"] || "--"),
            "detail": shellWindow && shellWindow.softwareRenderEnabled ? "software-safe shell" : "adaptive native shell",
            "tone": shellWindow && shellWindow.softwareRenderEnabled ? "warning" : "online"
        }
    ]

    implicitHeight: contentLayout.implicitHeight + ((shellWindow ? shellWindow.panelPadding : 18) * 2)

    function toneColor(tone) {
        return shellWindow ? shellWindow.toneColor(tone) : "#38b6ff"
    }

    function toneFill(tone) {
        return shellWindow ? shellWindow.toneFill(tone) : "#0d2234"
    }

    function rowObject(label) {
        for (var index = 0; index < rows.length; ++index) {
            var row = DataUtils.objectOrEmpty(rows[index])
            if (String(row["label"] || "") === label)
                return row
        }
        return ({})
    }

    function rowValue(label) {
        return String(rowObject(label)["value"] || "")
    }

    function rowTone(label) {
        return String(rowObject(label)["tone"] || "neutral")
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
                GradientStop { position: 0.0; color: shellWindow ? shellWindow.shellDockTop : "#14385c" }
                GradientStop { position: 0.48; color: shellWindow ? shellWindow.shellDockMid : "#0b1d31" }
                GradientStop { position: 1.0; color: shellWindow ? shellWindow.shellDockBottom : "#07111c" }
            }
            border.color: shellWindow ? shellWindow.panelGlowStrong : "#3292cf"
            border.width: 1
            implicitHeight: heroLayout.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 14) * 2)

            Rectangle {
                width: parent.width * 0.34
                height: parent.height * 0.8
                radius: width / 2
                color: "#3eb4ff"
                opacity: 0.12
                x: -width * 0.22
                y: -height * 0.2
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: shellWindow ? shellWindow.scaled(14) : 14
                anchors.rightMargin: shellWindow ? shellWindow.scaled(14) : 14
                height: shellWindow ? shellWindow.scaled(2) : 2
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.2; color: "rgba(58,174,255,0.06)" }
                    GradientStop { position: 0.5; color: "rgba(58,174,255,0.48)" }
                    GradientStop { position: 0.8; color: "rgba(58,174,255,0.08)" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: 0.72
            }

            GridLayout {
                id: heroLayout
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.cardPadding : 14
                columns: dualColumn ? 2 : 1
                columnSpacing: shellWindow ? shellWindow.zoneGap : 12
                rowSpacing: shellWindow ? shellWindow.compactGap : 8

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        Text {
                            Layout.fillWidth: true
                            text: panel["title"] || "左舷系统轨 / Left System Rail"
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
                        text: "左舷系统轨"
                        color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                        font.pixelSize: shellWindow ? shellWindow.sectionTitleSize : 24
                        font.bold: true
                        font.family: shellWindow ? shellWindow.displayFamily : "Noto Sans CJK SC"
                    }

                    Text {
                        text: "LEFT SYSTEM RAIL / BOARD HEALTH"
                        color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                        font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                        font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                    }

                    Text {
                        Layout.fillWidth: true
                        text: panel["summary"] || ""
                        color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                        font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                        wrapMode: Text.WordWrap
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#0b1a2a" }
                            GradientStop { position: 1.0; color: "#091321" }
                        }
                        border.color: root.toneColor(root.rowTone("链路档位"))
                        border.width: 1
                        implicitHeight: postureColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                        Column {
                            id: postureColumn
                            anchors.fill: parent
                            anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                            spacing: 2

                            Text {
                                text: "RAIL POSTURE / BOARD HEALTH"
                                color: shellWindow ? shellWindow.accentCyan : "#72f3ff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }

                            Text {
                                width: parent.width
                                text: (root.rowValue("链路档位") || "--") + " / " + (root.rowValue("心跳") || "--")
                                color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                font.bold: true
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                wrapMode: Text.WrapAnywhere
                            }

                            Text {
                                width: parent.width
                                text: root.rowValue("快照原因") || "只读镜像继续保持当前板态总线。"
                                color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                                font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: "#18405f"
                        opacity: 0.86
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        Repeater {
                            model: [
                                {
                                    "label": "会话",
                                    "value": root.rowValue("会话"),
                                    "tone": root.rowTone("会话")
                                },
                                {
                                    "label": "最近事件",
                                    "value": root.rowValue("最近事件"),
                                    "tone": root.rowTone("最近事件")
                                },
                                {
                                    "label": "心跳",
                                    "value": root.rowValue("心跳"),
                                    "tone": root.rowTone("心跳")
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
                                width: Math.max(shellWindow ? shellWindow.scaled(136) : 136, chipColumn.implicitWidth + (shellWindow ? shellWindow.scaled(22) : 22))

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
                                        font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                                        font.bold: true
                                        font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
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
                        GradientStop { position: 0.0; color: "#102539" }
                        GradientStop { position: 1.0; color: "#081321" }
                    }
                    border.color: "#235b84"
                    border.width: 1
                    implicitHeight: monitorColumn.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 14) * 2)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: parent.radius - 1
                        color: "transparent"
                        border.color: "#133450"
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
                            GradientStop { position: 0.22; color: shellWindow ? shellWindow.accentBlue : "#38b6ff" }
                            GradientStop { position: 0.72; color: shellWindow ? shellWindow.accentCyan : "#72f3ff" }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                        opacity: 0.78
                    }

                    Column {
                        id: monitorColumn
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.cardPadding : 14
                        spacing: shellWindow ? shellWindow.scaled(6) : 6

                        RowLayout {
                            width: parent.width
                            spacing: shellWindow ? shellWindow.compactGap : 8

                            Text {
                                Layout.fillWidth: true
                                text: "板端监视 / Left Monitor Rail"
                                color: shellWindow ? shellWindow.accentCyan : "#72f3ff"
                                font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            }

                            Rectangle {
                                radius: shellWindow ? shellWindow.edgeRadius : 10
                                color: "#091726"
                                border.color: "#1d547c"
                                border.width: 1
                                implicitWidth: monitorStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                                implicitHeight: monitorStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                                Text {
                                    id: monitorStamp
                                    anchors.centerIn: parent
                                    text: "3 NODES"
                                    color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                }
                            }
                        }

                        Repeater {
                            model: [
                                {
                                    "label": "作业统计",
                                    "value": root.rowValue("作业统计"),
                                    "tone": root.rowTone("作业统计")
                                },
                                {
                                    "label": "链路档位",
                                    "value": root.rowValue("链路档位"),
                                    "tone": root.rowTone("链路档位")
                                },
                                {
                                    "label": "事件时间",
                                    "value": root.rowValue("事件时间"),
                                    "tone": root.rowTone("事件时间")
                                }
                            ]

                            delegate: Rectangle {
                                readonly property var metric: modelData
                                width: parent.width
                                radius: shellWindow ? shellWindow.edgeRadius : 10
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: "#102133" }
                                    GradientStop { position: 1.0; color: "#091a2a" }
                                }
                                border.color: root.toneColor(metric["tone"])
                                border.width: 1
                                implicitHeight: metricColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    height: shellWindow ? shellWindow.scaled(2) : 2
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: "transparent" }
                                        GradientStop { position: 0.28; color: root.toneColor(metric["tone"]) }
                                        GradientStop { position: 0.72; color: Qt.lighter(root.toneColor(metric["tone"]), 1.16) }
                                        GradientStop { position: 1.0; color: "transparent" }
                                    }
                                    opacity: 0.74
                                }

                                Column {
                                    id: metricColumn
                                    anchors.fill: parent
                                    anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                                    spacing: 2

                                    Text {
                                        text: metric["label"]
                                        color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                        font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                        font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                                    }

                                    Text {
                                        width: parent.width
                                        text: metric["value"]
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
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.columnSpan: dualColumn ? 2 : 1
                    radius: shellWindow ? shellWindow.edgeRadius : 10
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#10253a" }
                        GradientStop { position: 0.48; color: "#0b1828" }
                        GradientStop { position: 1.0; color: "#081321" }
                    }
                    border.color: root.toneColor(root.rowTone("链路档位"))
                    border.width: 1
                    implicitHeight: stageFeedBusColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: parent.radius - 1
                        color: "transparent"
                        border.color: "#13334e"
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
                            GradientStop { position: 0.22; color: root.toneColor(root.rowTone("链路档位")) }
                            GradientStop { position: 0.72; color: Qt.lighter(root.toneColor(root.rowTone("链路档位")), 1.16) }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                        opacity: 0.78
                    }

                    ColumnLayout {
                        id: stageFeedBusColumn
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                        spacing: shellWindow ? shellWindow.compactGap : 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: shellWindow ? shellWindow.compactGap : 8

                            Text {
                                Layout.fillWidth: true
                                text: "左舷联动 / STAGE FEED BUS"
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
                                implicitWidth: stageFeedStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                                implicitHeight: stageFeedStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                                Text {
                                    id: stageFeedStamp
                                    anchors.centerIn: parent
                                    text: "LEFT -> CENTER"
                                    color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                                    font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                }
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.railBridgeLabel
                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                            font.bold: true
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.railBridgeDetail
                            color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                            wrapMode: Text.WordWrap
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: dualColumn ? 4 : 2
                            columnSpacing: shellWindow ? shellWindow.compactGap : 8
                            rowSpacing: shellWindow ? shellWindow.compactGap : 8

                            Repeater {
                                model: root.railBridgeModel.length

                                delegate: Rectangle {
                                    readonly property var bridgeData: root.railBridgeModel[index]
                                    Layout.fillWidth: true
                                    radius: shellWindow ? shellWindow.edgeRadius : 10
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: Qt.lighter(root.toneFill(bridgeData["tone"]), 1.14) }
                                        GradientStop { position: 1.0; color: root.toneFill(bridgeData["tone"]) }
                                    }
                                    border.color: root.toneColor(bridgeData["tone"])
                                    border.width: 1
                                    implicitHeight: bridgeMetricColumn.implicitHeight + ((shellWindow ? shellWindow.scaled(8) : 8) * 2)

                                    Column {
                                        id: bridgeMetricColumn
                                        anchors.fill: parent
                                        anchors.margins: shellWindow ? shellWindow.scaled(8) : 8
                                        spacing: 2

                                        Text {
                                            text: bridgeData["label"]
                                            color: shellWindow ? shellWindow.textMuted : "#4e7392"
                                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                        }

                                        Text {
                                            width: parent.width
                                            text: bridgeData["value"]
                                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                                            font.bold: true
                                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                                            wrapMode: Text.WrapAnywhere
                                        }

                                        Text {
                                            width: parent.width
                                            text: bridgeData["detail"]
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

        RowLayout {
            Layout.fillWidth: true
            spacing: shellWindow ? shellWindow.compactGap : 8

            Text {
                text: "状态矩阵 / STATUS MATRIX"
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
                implicitWidth: rowCountText.implicitWidth + ((shellWindow ? shellWindow.scaled(12) : 12) * 2)
                implicitHeight: rowCountText.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                Text {
                    id: rowCountText
                    anchors.centerIn: parent
                    text: String(rows.length) + " ROWS"
                    color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 10
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                }
            }
        }

        GridLayout {
            visible: root.hasRows
            Layout.fillWidth: true
            columns: dualColumn ? 2 : 1
            columnSpacing: shellWindow ? shellWindow.zoneGap : 12
            rowSpacing: shellWindow ? shellWindow.zoneGap : 12

            Repeater {
                model: rows

                delegate: Rectangle {
                    readonly property var rowData: modelData
                    readonly property bool wideCard: dualColumn && (String(rowData["label"] || "") === "作业统计" || String(rowData["label"] || "") === "快照原因")
                    Layout.fillWidth: true
                    Layout.columnSpan: wideCard ? 2 : 1
                    radius: shellWindow ? shellWindow.cardRadius : 14
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#0f2235" }
                        GradientStop { position: 1.0; color: "#0a1727" }
                    }
                    border.color: root.toneColor(rowData["tone"])
                    border.width: 1
                    implicitHeight: rowColumn.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 14) * 2)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: parent.radius - 1
                        color: "transparent"
                        border.color: "#112f49"
                        border.width: 1
                        opacity: 0.74
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: shellWindow ? shellWindow.scaled(3) : 3
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "transparent" }
                            GradientStop { position: 0.24; color: root.toneColor(rowData["tone"]) }
                            GradientStop { position: 0.72; color: Qt.lighter(root.toneColor(rowData["tone"]), 1.18) }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                        opacity: 0.74
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                        width: shellWindow ? shellWindow.scaled(4) : 4
                        radius: width / 2
                        color: root.toneColor(rowData["tone"])
                        opacity: 0.95
                    }

                    Rectangle {
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: shellWindow ? shellWindow.scaled(10) : 10
                        radius: shellWindow ? shellWindow.edgeRadius : 10
                        color: root.toneFill(rowData["tone"])
                        border.color: root.toneColor(rowData["tone"])
                        border.width: 1
                        implicitWidth: rowToneText.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                        implicitHeight: rowToneText.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                        Text {
                            id: rowToneText
                            anchors.centerIn: parent
                            text: String(rowData["tone"] || "neutral").toUpperCase()
                            color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        }
                    }

                    Column {
                        id: rowColumn
                        anchors.fill: parent
                        anchors.margins: shellWindow ? shellWindow.cardPadding : 14
                        anchors.leftMargin: (shellWindow ? shellWindow.cardPadding : 14) + (shellWindow ? shellWindow.scaled(8) : 8)
                        spacing: shellWindow ? shellWindow.scaled(4) : 4

                        Text {
                            text: rowData["label"] || ""
                            color: shellWindow ? shellWindow.textMuted : "#4e7392"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                        }

                        Text {
                            width: parent.width
                            text: rowData["value"] || ""
                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                            font.pixelSize: shellWindow ? shellWindow.bodySize : 13
                            font.bold: true
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }

        Rectangle {
            visible: !root.hasRows
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: shellWindow ? shellWindow.scaled(230) : 230
            radius: shellWindow ? shellWindow.cardRadius : 14
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
                anchors.margins: shellWindow ? shellWindow.cardPadding : 14
                spacing: shellWindow ? shellWindow.compactGap : 8

                RowLayout {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "零数据待机 / STANDBY WALL"
                            color: shellWindow ? shellWindow.accentBlue : "#38b6ff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                            font.letterSpacing: shellWindow ? shellWindow.scaled(1) : 1
                        }

                        Text {
                            text: "左舷系统轨等待板端矩阵回填"
                            color: shellWindow ? shellWindow.textStrong : "#f4fbff"
                            font.pixelSize: shellWindow ? shellWindow.bodyEmphasisSize : 14
                            font.bold: true
                            font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                        }

                        Text {
                            width: parent.width
                            text: "当前继续沿用已知合同字段与镜像会话，不虚构未抵达的板端统计；一旦数据回填，状态矩阵会直接接管这一段空间。"
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
                            text: "ARCHIVE BUS"
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
                            width: Math.max(shellWindow ? shellWindow.scaled(170) : 170, standbyChipColumn.implicitWidth + (shellWindow ? shellWindow.scaled(22) : 22))

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
            radius: shellWindow ? shellWindow.cardRadius : 14
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#0b1b2d" }
                GradientStop { position: 1.0; color: "#091421" }
            }
            border.color: "#1f557c"
            border.width: 1
            implicitHeight: footerColumn.implicitHeight + ((shellWindow ? shellWindow.cardPadding : 14) * 2)

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
                id: footerColumn
                anchors.fill: parent
                anchors.margins: shellWindow ? shellWindow.cardPadding : 14
                spacing: shellWindow ? shellWindow.scaled(4) : 4

                RowLayout {
                    width: parent.width
                    spacing: shellWindow ? shellWindow.compactGap : 8

                    Text {
                        text: "真实性边界 / EVIDENCE BOUNDARY"
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
                        implicitWidth: evidenceStamp.implicitWidth + ((shellWindow ? shellWindow.scaled(10) : 10) * 2)
                        implicitHeight: evidenceStamp.implicitHeight + ((shellWindow ? shellWindow.scaled(5) : 5) * 2)

                        Text {
                            id: evidenceStamp
                            anchors.centerIn: parent
                            text: rowValue("会话") || "MIRROR ONLY"
                            color: shellWindow ? shellWindow.textPrimary : "#d5eeff"
                            font.pixelSize: shellWindow ? shellWindow.captionSize : 9
                            font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                        }
                    }
                }

                Text {
                    width: parent.width
                    text: panel["truth_note"] || ""
                    visible: text.length > 0
                    color: shellWindow ? shellWindow.textSecondary : "#83acc8"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                    font.family: shellWindow ? shellWindow.uiFamily : "Noto Sans CJK SC"
                    wrapMode: Text.WordWrap
                }

                Text {
                    width: parent.width
                    text: panel["snapshot_path"] || ""
                    visible: text.length > 0
                    color: shellWindow ? shellWindow.textMuted : "#4e7392"
                    font.pixelSize: shellWindow ? shellWindow.captionSize : 11
                    font.family: shellWindow ? shellWindow.monoFamily : "JetBrains Mono"
                    wrapMode: Text.WrapAnywhere
                }
            }
        }
    }
}
