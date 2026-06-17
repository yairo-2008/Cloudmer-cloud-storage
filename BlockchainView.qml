import QtQuick
import QtQuick.Controls
import QtQuick.Layouts 1.15

/**
 * BlockchainView.qml
 * ------------------
 * Displays the full CloudMer blockchain as a vertical list of cards.
 * Each card shows:
 *   • Block index + shortened hash
 *   • Filename & owner (from the primary UPLOAD transaction, if any)
 *   • ISO timestamp
 *   • PoW verification badge  (green "Verified" / red "Invalid")
 *
 * Usage — wire up in parent QML:
 *
 *   BlockchainView {
 *       anchors.fill: parent
 *       // blockChain property is populated by onBlockchainUpdated
 *   }
 *
 *   Connections {
 *       target: backend
 *       function onBlockchainUpdated(chain) { blockchainView.blockChain = chain }
 *   }
 */
Item {
    id: root

    // ── Public API ───────────────────────────────────────────────────────────
    property var blockChain: []   // array of block-summary dicts from BLCH slot

    // ── Header ───────────────────────────────────────────────────────────────
    Rectangle {
        id: header
        width: parent.width; height: 52
        color: "#f8fafc"
        border.color: "#e2e8f0"; border.width: 1

        Row {
            anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 16
            spacing: 12

            Text {
                text: "⛓  Blockchain"
                font.pixelSize: 16; font.bold: true; color: "#1e293b"
                anchors.verticalCenter: parent.verticalCenter
            }

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: heightLabel.implicitWidth + 16; height: 24; radius: 12
                color: "#e0f2fe"
                Text {
                    id: heightLabel
                    anchors.centerIn: parent
                    text: root.blockChain.length + " block" + (root.blockChain.length !== 1 ? "s" : "")
                    color: "#0369a1"; font.pixelSize: 12; font.bold: true
                }
            }

            Item { width: 1; Layout.fillWidth: true }

            // Refresh button
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 32; height: 32; radius: 16
                color: refreshHover.containsMouse ? "#e2e8f0" : "transparent"
                Behavior on color { ColorAnimation { duration: 80 } }
                HoverHandler { id: refreshHover }
                Text { anchors.centerIn: parent; text: "⟳"; color: "#64748b"; font.pixelSize: 18 }
                MouseArea { anchors.fill: parent; onClicked: backend.getBlockchain() }
                ToolTip.visible: refreshHover.hovered; ToolTip.text: "Refresh chain"
            }
        }
    }

    // ── Chain List ───────────────────────────────────────────────────────────
    ListView {
        id: chainView
        anchors.top: header.bottom; anchors.bottom: parent.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 16
        spacing: 10
        clip: true

        // Show newest block at the top
        model: root.blockChain
        verticalLayoutDirection: ListView.BottomToTop

        delegate: BlockCard {
            width: chainView.width
            blockData: modelData
        }

        // Empty state
        Item {
            anchors.centerIn: parent
            width: 260; height: 160
            visible: chainView.count === 0

            Column {
                anchors.centerIn: parent; spacing: 10
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "⛓"; font.pixelSize: 44 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "No blocks yet"
                    color: "#1e293b"; font.pixelSize: 15; font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Upload a file to create the first block"
                    color: "#64748b"; font.pixelSize: 12
                }
            }
        }

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    }

    // ── Block Card Component ─────────────────────────────────────────────────
    component BlockCard: Rectangle {
        property var blockData: ({})

        // Derived display values
        readonly property bool  isGenesis:  blockData.index === 0
        readonly property bool  isVerified: blockData.is_verified === true
        readonly property string shortHash: {
            var h = blockData.hash || ""
            return h.length >= 16 ? h.substring(0, 8) + "…" + h.substring(h.length - 8) : h
        }
        readonly property string shortFileHash: {
            var fh = blockData.file_hash || ""
            return fh.length >= 12 ? fh.substring(0, 12) + "…" : (fh || "—")
        }
        readonly property string formattedTime: {
            var ts = blockData.timestamp
            if (!ts) return "—"
            var d = new Date(ts * 1000)
            return d.toLocaleDateString() + "  " + d.toLocaleTimeString()
        }

        height: cardColumn.implicitHeight + 24
        radius: 12
        color: "#ffffff"
        border.color: isVerified ? "#bbf7d0" : "#fecaca"
        border.width: 1

        // Subtle left accent bar
        Rectangle {
            width: 4; height: parent.height; radius: 2
            anchors.left: parent.left
            color: isGenesis ? "#6366f1" : (isVerified ? "#22c55e" : "#ef4444")
        }

        Column {
            id: cardColumn
            anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 20; anchors.rightMargin: 16
            anchors.top: parent.top; anchors.topMargin: 14
            spacing: 8

            // ── Row 1: index + hash + verified badge ──────────────────────
            Row {
                width: parent.width; spacing: 10

                // Block index pill
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: idxLabel.implicitWidth + 14; height: 22; radius: 11
                    color: isGenesis ? "#ede9fe" : "#f1f5f9"
                    Text {
                        id: idxLabel
                        anchors.centerIn: parent
                        text: isGenesis ? "Genesis" : ("#" + blockData.index)
                        color: isGenesis ? "#7c3aed" : "#475569"
                        font.pixelSize: 11; font.bold: true
                    }
                }

                // Block hash (monospace)
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: shortHash
                    color: "#334155"; font.pixelSize: 12
                    font.family: "Courier New, monospace"
                    width: parent.width - verifiedBadge.width - 90
                    elide: Text.ElideRight
                }

                // PoW verification badge
                Rectangle {
                    id: verifiedBadge
                    anchors.verticalCenter: parent.verticalCenter
                    width: badgeText.implicitWidth + 16; height: 22; radius: 11
                    color: isVerified ? "#dcfce7" : "#fee2e2"
                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: isVerified ? "✓ Verified" : "✗ Invalid"
                        color: isVerified ? "#15803d" : "#b91c1c"
                        font.pixelSize: 11; font.bold: true
                    }
                }
            }

            // ── Row 2: transaction data ────────────────────────────────────
            Row {
                width: parent.width; spacing: 24
                visible: !isGenesis && (blockData.file_name || blockData.sender_id)

                Column {
                    spacing: 2
                    Text { text: "File"; color: "#94a3b8"; font.pixelSize: 10 }
                    Text {
                        text: blockData.file_name || "—"
                        color: "#1e293b"; font.pixelSize: 12
                        elide: Text.ElideRight; width: 200
                    }
                }

                Column {
                    spacing: 2
                    Text { text: "Owner"; color: "#94a3b8"; font.pixelSize: 10 }
                    Text {
                        text: blockData.sender_id || "—"
                        color: "#1e293b"; font.pixelSize: 12
                        elide: Text.ElideRight; width: 180
                    }
                }

                Column {
                    spacing: 2
                    Text { text: "Txs"; color: "#94a3b8"; font.pixelSize: 10 }
                    Text {
                        text: blockData.tx_count !== undefined ? blockData.tx_count : "—"
                        color: "#1e293b"; font.pixelSize: 12
                    }
                }
            }

            // ── Row 3: file hash + timestamp ──────────────────────────────
            Row {
                width: parent.width; spacing: 24

                Column {
                    spacing: 2
                    visible: !isGenesis && blockData.file_hash
                    Text { text: "SHA-256"; color: "#94a3b8"; font.pixelSize: 10 }
                    Text {
                        text: shortFileHash
                        color: "#1a73e8"; font.pixelSize: 11
                        font.family: "Courier New, monospace"
                        ToolTip.visible: fhHov.hovered
                        ToolTip.text: blockData.file_hash || ""
                        HoverHandler { id: fhHov }
                    }
                }

                Column {
                    spacing: 2
                    Text { text: "Timestamp"; color: "#94a3b8"; font.pixelSize: 10 }
                    Text { text: formattedTime; color: "#475569"; font.pixelSize: 11 }
                }
            }

            // ── Spacer ────────────────────────────────────────────────────
            Item { width: 1; height: 2 }
        }
    }
}
