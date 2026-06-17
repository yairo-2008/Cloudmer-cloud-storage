import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

ApplicationWindow {
    visible: true
    width: 1200
    height: 700
    title: "CLOUDMER"
    color: "#ffffff"

    property string loggedInUser: ""

    Connections {
        target: backend
        function onLoginSuccess(name) {
            loggedInUser = name
            rootStack.push(dashboardPage)
        }
        function onLoginFailed(error) {
            statusText.color = "#d93025"
            statusText.text = error
        }
        function onSignupSuccess(msg) {
            signupStatus.color = "#1e8e3e"
            signupStatus.text = msg
        }
        function onSignupFailed(error) {
            signupStatus.color = "#d93025"
            signupStatus.text = error
        }
    }

    StackView {
        id: rootStack
        anchors.fill: parent
        initialItem: loginPage
        pushEnter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 300 } }
        pushExit:  Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 300 } }
        popEnter:  Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 300 } }
        popExit:   Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 300 } }
    }

    // ===================== LOGIN PAGE =====================
    Component {
        id: loginPage
        Item {
            Rectangle {
                width: 600; height: 600; radius: 300
                x: -200; y: -200; color: "#1e293b"; opacity: 0.5
            }
            Rectangle {
                width: 450; height: 580
                anchors.centerIn: parent
                color: "#1e293b"; radius: 30
                border.color: "#334155"; border.width: 1
                Column {
                    anchors.fill: parent; anchors.margins: 50; spacing: 20
                    Item {
                        width: parent.width; height: 60
                        Row {
                            anchors.centerIn: parent; spacing: 10
                            Rectangle { width: 30; height: 30; radius: 6; color: "#38bdf8" }
                            Text { text: "CLOUDMER"; color: "white"; font.pixelSize: 28; font.letterSpacing: 2; font.bold: true }
                        }
                    }
                    Text {
                        text: authStack.depth === 1 ? "Welcome Back" : "Create Account"
                        color: "#94a3b8"; font.pixelSize: 16
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    StackView {
                        id: authStack
                        width: parent.width; height: 340
                        initialItem: loginFields
                        pushEnter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 200 } }
                        popExit:   Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 200 } }
                    }
                }
            }
            Component {
                id: loginFields
                Column {
                    spacing: 15
                    Connections {
                        target: backend
                        function onLoginFailed(error) { statusText.color = "#f87171"; statusText.text = error }
                    }
                    TextField {
                        id: userIn; placeholderText: "Email address"
                        width: 350; height: 50; color: "white"; font.pixelSize: 15
                        background: Rectangle { color: "#0f172a"; radius: 12; border.color: userIn.activeFocus ? "#38bdf8" : "#334155" }
                    }
                    TextField {
                        id: passIn; placeholderText: "Password"; echoMode: TextInput.Password
                        width: 350; height: 50; color: "white"; font.pixelSize: 15
                        background: Rectangle { color: "#0f172a"; radius: 12; border.color: passIn.activeFocus ? "#38bdf8" : "#334155" }
                    }
                    Text {
                        id: statusText; text: ""; color: "#f87171"; font.pixelSize: 13
                        width: 350; wrapMode: Text.WordWrap
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Button {
                        width: 350; height: 55
                        onClicked: { statusText.text = ""; backend.login(userIn.text, passIn.text) }
                        background: Rectangle {
                            radius: 12
                            color: parent.pressed ? "#0284c7" : "#38bdf8"
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                        contentItem: Text { text: "Sign In"; color: "#0f172a"; font.bold: true; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    }
                    Text {
                        text: "New here? <font color='#38bdf8'>Create an account</font>"
                        color: "#94a3b8"; font.pixelSize: 13
                        anchors.horizontalCenter: parent.horizontalCenter
                        MouseArea { anchors.fill: parent; onClicked: { statusText.text = ""; authStack.push(registerFields) } }
                    }
                }
            }
            Component {
                id: registerFields
                Column {
                    spacing: 12
                    Connections {
                        target: backend
                        function onSignupSuccess(msg) { signupStatus.color = "#4ade80"; signupStatus.text = msg }
                        function onSignupFailed(error) { signupStatus.color = "#f87171"; signupStatus.text = error }
                    }
                    TextField {
                        id: nameIn; placeholderText: "Full Name"
                        width: 350; height: 45; color: "white"
                        background: Rectangle { color: "#0f172a"; radius: 10; border.color: nameIn.activeFocus ? "#38bdf8" : "#334155" }
                    }
                    TextField {
                        id: emailIn; placeholderText: "Email"
                        width: 350; height: 45; color: "white"
                        background: Rectangle { color: "#0f172a"; radius: 10; border.color: emailIn.activeFocus ? "#38bdf8" : "#334155" }
                    }
                    TextField {
                        id: passIn2; placeholderText: "Password (min 6 characters)"; echoMode: TextInput.Password
                        width: 350; height: 45; color: "white"
                        background: Rectangle { color: "#0f172a"; radius: 10; border.color: passIn2.activeFocus ? "#38bdf8" : "#334155" }
                    }
                    Text {
                        id: signupStatus; text: ""; color: "#f87171"; font.pixelSize: 13
                        width: 350; wrapMode: Text.WordWrap
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Button {
                        width: 350; height: 50
                        onClicked: { signupStatus.text = ""; backend.signup(nameIn.text, emailIn.text, passIn2.text) }
                        background: Rectangle { radius: 10; color: parent.pressed ? "#0284c7" : "#38bdf8"; Behavior on color { ColorAnimation { duration: 150 } } }
                        contentItem: Text { text: "Get Started"; color: "#0f172a"; font.bold: true; font.pixelSize: 15; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    }
                    Button {
                        flat: true; width: 350
                        onClicked: { signupStatus.text = ""; authStack.pop() }
                        contentItem: Text { text: "← Back to Login"; color: "#94a3b8"; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter }
                    }
                }
            }
        }
    }

    // ===================== DASHBOARD PAGE =====================
    Component {
        id: dashboardPage

        Item {
            anchors.fill: parent

            // ── STATE ──────────────────────────────────────────────────
            property string currentView: "home"
            property var    chainData:   []

            ListModel { id: fileModel }
            ListModel { id: starredModel }
            ListModel { id: trashModel }
            ListModel { id: recentModel }

            FileDialog {
                id: fileDialog
                title: "Choose a file to upload"
                onAccepted: {
                    var path = fileDialog.selectedFile.toString().replace("file:///", "")
                    statusBar.text = "Uploading..."
                    statusBar.color = "#1a73e8"
                    backend.uploadFile(path)
                }
            }

            // ── File Info Panel (blockchain metadata) ─────────────────
            Rectangle {
                id: fileInfoPanel
                visible: false
                z: 100
                width: 420; height: 320
                anchors.centerIn: parent
                radius: 16; color: "#ffffff"
                border.color: "#dadce0"; border.width: 1

                // Drop shadow effect
                layer.enabled: true
                layer.effect: null

                property string infoFilename:  ""
                property string infoFileHash:  ""
                property string infoFileSize:  ""
                property string infoOwner:     ""
                property string infoTimestamp: ""
                property var    infoHistory:   []

                // ── Dim background ────────────────────────────────────
                MouseArea {
                    anchors.fill: parent
                    onClicked: {}   // absorb clicks
                }

                Column {
                    anchors.fill: parent; anchors.margins: 28; spacing: 14

                    // Header
                    Row {
                        width: parent.width
                        Text {
                            text: "📋  File Info"
                            font.pixelSize: 16; font.bold: true; color: "#202124"
                            width: parent.width - 32
                        }
                        Rectangle {
                            width: 28; height: 28; radius: 14
                            color: closeHov.containsMouse ? "#f1f3f4" : "transparent"
                            Behavior on color { ColorAnimation { duration: 80 } }
                            HoverHandler { id: closeHov }
                            Text { anchors.centerIn: parent; text: "✕"; color: "#5f6368"; font.pixelSize: 14; font.bold: true }
                            MouseArea { anchors.fill: parent; onClicked: fileInfoPanel.visible = false }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#e0e0e0" }

                    // Info rows
                    Grid {
                        columns: 2; columnSpacing: 12; rowSpacing: 10; width: parent.width

                        Text { text: "Name";      color: "#5f6368"; font.pixelSize: 13 }
                        Text { text: fileInfoPanel.infoFilename;  color: "#202124"; font.pixelSize: 13; elide: Text.ElideRight; width: 240 }

                        Text { text: "Size";      color: "#5f6368"; font.pixelSize: 13 }
                        Text { text: fileInfoPanel.infoFileSize;   color: "#202124"; font.pixelSize: 13 }

                        Text { text: "Owner";     color: "#5f6368"; font.pixelSize: 13 }
                        Text { text: fileInfoPanel.infoOwner;      color: "#202124"; font.pixelSize: 13; elide: Text.ElideRight; width: 240 }

                        Text { text: "Uploaded";  color: "#5f6368"; font.pixelSize: 13 }
                        Text { text: fileInfoPanel.infoTimestamp;  color: "#202124"; font.pixelSize: 13 }

                        Text { text: "SHA-256";   color: "#5f6368"; font.pixelSize: 13 }
                        Text {
                            text: fileInfoPanel.infoFileHash.length > 16
                                  ? fileInfoPanel.infoFileHash.substring(0, 16) + "..."
                                  : fileInfoPanel.infoFileHash
                            color: "#1a73e8"; font.pixelSize: 12; font.family: "Monospace"
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#e0e0e0" }

                    // History title
                    Text { text: "Transaction History (" + fileInfoPanel.infoHistory.length + " events)"; color: "#5f6368"; font.pixelSize: 12 }

                    // History list
                    ListView {
                        width: parent.width; height: 60; clip: true
                        model: fileInfoPanel.infoHistory
                        delegate: Row {
                            spacing: 8; width: parent.width
                            Text {
                                text: modelData["type"] || ""
                                color: "#1a73e8"; font.pixelSize: 11; font.bold: true; width: 90
                            }
                            Text {
                                text: {
                                    var ts = modelData["timestamp"]
                                    if (!ts) return ""
                                    var d = new Date(ts * 1000)
                                    return d.toLocaleDateString() + " " + d.toLocaleTimeString()
                                }
                                color: "#5f6368"; font.pixelSize: 11
                            }
                        }
                    }
                }
            }

            // Connections for blockchain signals
            Connections {
                target: backend

                function onUploadProgress(percent) { statusBar.text = "Uploading... " + percent + "%"; statusBar.color = "#1a73e8" }
                function onUploadSuccess(result) {
                    var parts = result.split("|")
                    var filename  = parts[0]
                    var file_hash = parts.length > 1 ? parts[1] : ""
                    statusBar.text  = "✓ " + filename + " uploaded!"
                    statusBar.color = "#1e8e3e"
                    backend.getFileList()
                }
                function onUploadFailed(error) { statusBar.text = "✗ " + error; statusBar.color = "#d93025" }

                function onFileListReady(files) {
                    fileModel.clear()
                    recentModel.clear()
                    for (var i = 0; i < files.length; i++) {
                        fileModel.append(files[i])
                        recentModel.append(files[i])
                    }
                }
                function onStarredListReady(files) {
                    starredModel.clear()
                    for (var i = 0; i < files.length; i++) starredModel.append(files[i])
                }
                function onTrashListReady(files) {
                    trashModel.clear()
                    for (var i = 0; i < files.length; i++) trashModel.append(files[i])
                }
                function onStarToggled(filename, isStarred) {
                    statusBar.text  = isStarred ? ("⭐ " + filename + " starred") : (filename + " unstarred")
                    statusBar.color = "#f9ab00"
                    backend.getFileList()
                }
                function onFileDeleted(filename) {
                    statusBar.text  = filename + " moved to Trash"
                    statusBar.color = "#5f6368"
                    backend.getFileList()
                    backend.getTrashFiles()
                }
                function onFileRestored(filename) {
                    statusBar.text  = "✓ " + filename + " restored"
                    statusBar.color = "#1e8e3e"
                    backend.getFileList()
                    backend.getTrashFiles()
                }
                function onFilePurged(filename) {
                    statusBar.text  = filename + " permanently deleted"
                    statusBar.color = "#d93025"
                    backend.getTrashFiles()
                }

                // ── Blockchain chain updates ──────────────────────────
                function onBlockchainUpdated(chain) {
                    chainData = chain
                    // If the user is already looking at the blockchain view,
                    // the binding on BlockchainView.blockChain updates automatically.
                    if (currentView === "blockchain") {
                        statusBar.text  = "Chain updated — " + chain.length + " block(s)"
                        statusBar.color = "#1a73e8"
                    }
                }

                // ── Blockchain metadata panel ─────────────────────────
                function onFileMetaReady(meta) {
                    fileInfoPanel.infoFilename  = meta["file_name"]  || ""
                    fileInfoPanel.infoFileHash  = meta["file_hash"]  || ""
                    fileInfoPanel.infoFileSize  = meta["file_size"] !== undefined
                                                  ? (meta["file_size"] + " B") : ""
                    fileInfoPanel.infoOwner     = meta["owner"]      || ""
                    var ts = meta["timestamp"]
                    if (ts) {
                        var d = new Date(ts * 1000)
                        fileInfoPanel.infoTimestamp = d.toLocaleDateString() + " " + d.toLocaleTimeString()
                    } else {
                        fileInfoPanel.infoTimestamp = ""
                    }
                    fileInfoPanel.visible = true
                }
                function onFileHistoryReady(history) {
                    fileInfoPanel.infoHistory = history
                }
            }

            // ── TOP HEADER ─────────────────────────────────────────────
            Rectangle {
                id: topHeader
                width: parent.width; height: 64
                color: "#ffffff"
                border.color: "#e0e0e0"; border.width: 1
                z: 10

                Row {
                    anchors.left: parent.left; anchors.leftMargin: 16
                    anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    Rectangle { width: 22; height: 22; radius: 4; color: "#1a73e8"; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "CLOUDMER"; font.pixelSize: 20; font.bold: true; color: "#202124"; anchors.verticalCenter: parent.verticalCenter }
                }

                Rectangle {
                    width: 480; height: 44; anchors.centerIn: parent; radius: 24
                    color: searchField.activeFocus ? "#ffffff" : "#f1f3f4"
                    border.color: searchField.activeFocus ? "#1a73e8" : "transparent"
                    border.width: searchField.activeFocus ? 2 : 0
                    Row {
                        anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 10
                        Text { text: "🔍"; font.pixelSize: 16; anchors.verticalCenter: parent.verticalCenter; color: "#5f6368" }
                        TextField {
                            id: searchField; placeholderText: "Search in CLOUDMER"
                            width: parent.width - 50; anchors.verticalCenter: parent.verticalCenter
                            color: "#202124"; font.pixelSize: 15
                            background: Rectangle { color: "transparent" }
                        }
                    }
                }

                Rectangle {
                    width: 36; height: 36; radius: 18; color: "#1a73e8"
                    anchors.right: parent.right; anchors.rightMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    Text { anchors.centerIn: parent; text: loggedInUser.length > 0 ? loggedInUser[0].toUpperCase() : "?"; color: "white"; font.bold: true; font.pixelSize: 15 }
                    MouseArea {
                        anchors.fill: parent; hoverEnabled: true
                        onClicked: rootStack.pop()
                        ToolTip.visible: containsMouse; ToolTip.text: "Logout (" + loggedInUser + ")"
                    }
                }
            }

            // ── SIDEBAR ────────────────────────────────────────────────
            Rectangle {
                id: sidebar
                width: 200
                anchors.top: topHeader.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left
                color: "#ffffff"

                Column {
                    anchors.fill: parent; anchors.topMargin: 12; spacing: 2

                    Rectangle {
                        width: 130; height: 48
                        anchors.left: parent.left; anchors.leftMargin: 12
                        radius: 24; color: newHov.containsMouse ? "#e8f0fe" : "#ffffff"
                        border.color: "#dadce0"; border.width: 1
                        Behavior on color { ColorAnimation { duration: 100 } }
                        HoverHandler { id: newHov }
                        Row {
                            anchors.centerIn: parent; spacing: 8
                            Text { text: "+"; color: "#202124"; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "New";  color: "#202124"; font.pixelSize: 14; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea { anchors.fill: parent; onClicked: fileDialog.open() }
                    }

                    Item { width: 1; height: 10 }

                    Repeater {
                        model: [
                            { icon: "🏠", label: "Home",       view: "home"       },
                            { icon: "💾", label: "My Drive",   view: "drive"      },
                            { icon: "💻", label: "Computers",  view: "computers"  },
                            { icon: "👥", label: "Shared",     view: "shared"     },
                            { icon: "🕐", label: "Recent",     view: "recent"     },
                            { icon: "⭐", label: "Starred",    view: "starred"    },
                            { icon: "🗑", label: "Trash",      view: "trash"      },
                            { icon: "⛓", label: "Blockchain", view: "blockchain" }
                        ]

                        delegate: Rectangle {
                            width: parent.width - 12; height: 40
                            anchors.left: parent.left; anchors.leftMargin: 6
                            radius: 20
                            color: currentView === modelData.view ? "#e8f0fe" : (navHov.containsMouse ? "#f1f3f4" : "transparent")
                            Behavior on color { ColorAnimation { duration: 100 } }
                            HoverHandler { id: navHov }

                            Row {
                                anchors.fill: parent; anchors.leftMargin: 16; spacing: 14
                                Text { text: modelData.icon; font.pixelSize: 15; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: modelData.label; font.pixelSize: 13
                                    color: currentView === modelData.view ? "#1a73e8" : "#202124"
                                    font.bold: currentView === modelData.view
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    currentView = modelData.view
                                    statusBar.text = ""
                                    fileInfoPanel.visible = false
                                    if (modelData.view === "home" || modelData.view === "drive" || modelData.view === "shared") {
                                        backend.getFileList()
                                    } else if (modelData.view === "recent") {
                                        backend.getFileList()
                                    } else if (modelData.view === "starred") {
                                        backend.getStarredFiles()
                                    } else if (modelData.view === "trash") {
                                        backend.getTrashFiles()
                                    } else if (modelData.view === "blockchain") {
                                        backend.getBlockchain()
                                    } else if (modelData.view === "computers") {
                                        statusBar.text  = "Computers sync coming soon"
                                        statusBar.color = "#5f6368"
                                    }
                                }
                            }
                        }
                    }

                    Item { width: 1; height: 16 }
                    Rectangle { width: parent.width - 24; height: 1; color: "#e0e0e0"; anchors.horizontalCenter: parent.horizontalCenter }
                    Item { width: 1; height: 12 }

                }
            }

            // ── BLOCKCHAIN VIEW (overlays main content) ────────────────
            BlockchainView {
                id: blockchainView
                visible: currentView === "blockchain"
                anchors.left: sidebar.right; anchors.right: parent.right
                anchors.top: topHeader.bottom; anchors.bottom: parent.bottom
                blockChain: chainData
                z: 1
            }

            // ── MAIN CONTENT ───────────────────────────────────────────
            Rectangle {
                anchors.left: sidebar.right; anchors.right: parent.right
                anchors.top: topHeader.bottom; anchors.bottom: parent.bottom
                color: "#ffffff"
                visible: currentView !== "blockchain"

                Column {
                    anchors.fill: parent; anchors.margins: 20; spacing: 0

                    Text {
                        id: statusBar; text: ""; color: "#1a73e8"; font.pixelSize: 12
                        height: text === "" ? 0 : 24
                    }

                    Item {
                        width: parent.width; height: 48

                        Text {
                            text: {
                                if (currentView === "home")      return "Welcome, " + loggedInUser
                                if (currentView === "drive")     return "My Drive"
                                if (currentView === "shared")    return "Shared with me"
                                if (currentView === "recent")    return "Recent"
                                if (currentView === "starred")   return "Starred"
                                if (currentView === "trash")     return "Trash"
                                if (currentView === "computers") return "Computers"
                                return "CLOUDMER"
                            }
                            font.pixelSize: 18; color: "#202124"
                            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                        }

                        Row {
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 4

                            Rectangle {
                                visible: currentView === "trash"
                                width: 120; height: 36; radius: 18
                                color: emptyHov.containsMouse ? "#fad2cf" : "#fce8e6"
                                Behavior on color { ColorAnimation { duration: 100 } }
                                HoverHandler { id: emptyHov }
                                Text { anchors.centerIn: parent; text: "Empty Trash"; color: "#d93025"; font.pixelSize: 13; font.bold: true }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: { statusBar.text = "Trash emptied"; statusBar.color = "#d93025"; trashModel.clear() }
                                }
                            }

                            Rectangle {
                                width: 36; height: 36; radius: 18
                                color: refHov.containsMouse ? "#f1f3f4" : "transparent"
                                Behavior on color { ColorAnimation { duration: 100 } }
                                HoverHandler { id: refHov }
                                Text { anchors.centerIn: parent; text: "⟳"; color: "#5f6368"; font.pixelSize: 18 }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        if (currentView === "starred")    backend.getStarredFiles()
                                        else if (currentView === "trash") backend.getTrashFiles()
                                        else                              backend.getFileList()
                                    }
                                }
                            }

                            Rectangle {
                                visible: currentView !== "trash"
                                width: 100; height: 36; radius: 18
                                color: upHov.containsMouse ? "#c2d7f5" : "#e8f0fe"
                                Behavior on color { ColorAnimation { duration: 100 } }
                                HoverHandler { id: upHov }
                                Row {
                                    anchors.centerIn: parent; spacing: 6
                                    Text { text: "↑"; color: "#1a73e8"; font.pixelSize: 16; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Upload"; color: "#1a73e8"; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                }
                                MouseArea { anchors.fill: parent; onClicked: fileDialog.open() }
                            }
                        }
                    }

                    // Column headers
                    Rectangle {
                        width: parent.width; height: 40; color: "transparent"
                        Rectangle { width: parent.width; height: 1; color: "#e0e0e0"; anchors.bottom: parent.bottom }
                        Row {
                            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                            Text { text: "Name";     color: "#5f6368"; font.pixelSize: 12; width: 280; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Owner";    color: "#5f6368"; font.pixelSize: 12; width: 140; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Modified"; color: "#5f6368"; font.pixelSize: 12; width: 120; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Size";     color: "#5f6368"; font.pixelSize: 12; width: 90;  anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Hash";     color: "#5f6368"; font.pixelSize: 12; width: 120; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "";         color: "#5f6368"; font.pixelSize: 12; width: 130; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }

                    // ── FILE LIST ──────────────────────────────────────
                    ListView {
                        id: fileListView
                        width: parent.width
                        height: parent.height - 130
                        clip: true; spacing: 0

                        model: {
                            if (currentView === "starred") return starredModel
                            if (currentView === "trash")   return trashModel
                            if (currentView === "recent")  return recentModel
                            return fileModel
                        }

                        delegate: Rectangle {
                            width: ListView.view.width; height: 44
                            color: rowHov.containsMouse ? "#f1f3f4" : "transparent"
                            Behavior on color { ColorAnimation { duration: 80 } }
                            HoverHandler { id: rowHov }
                            Rectangle { width: parent.width; height: 1; color: "#f1f3f4"; anchors.bottom: parent.bottom }

                            Row {
                                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12

                                // Icon + Name
                                Row {
                                    width: 280; spacing: 10; anchors.verticalCenter: parent.verticalCenter
                                    Rectangle {
                                        width: 28; height: 28; radius: 4; anchors.verticalCenter: parent.verticalCenter
                                        color: {
                                            var ext = name.split('.').pop().toLowerCase()
                                            if (ext === "pdf")  return "#ea4335"
                                            if (ext === "docx" || ext === "doc") return "#4285f4"
                                            if (ext === "xlsx" || ext === "xls") return "#34a853"
                                            if (ext === "jpg"  || ext === "png" || ext === "jpeg") return "#fbbc04"
                                            if (ext === "mp4"  || ext === "avi") return "#ea4335"
                                            if (ext === "zip"  || ext === "rar") return "#9e9e9e"
                                            return "#1a73e8"
                                        }
                                        Text { anchors.centerIn: parent; text: name.split('.').pop().toUpperCase().substring(0,3); color: "white"; font.pixelSize: 8; font.bold: true }
                                    }
                                    Text { text: name; color: "#202124"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; width: 240 }
                                }

                                Text { text: loggedInUser; color: "#5f6368"; font.pixelSize: 13; width: 140; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight }
                                Text { text: modified;     color: "#5f6368"; font.pixelSize: 13; width: 120; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: size;         color: "#5f6368"; font.pixelSize: 13; width: 90;  anchors.verticalCenter: parent.verticalCenter }

                                // Short hash
                                Text {
                                    text: (file_hash && file_hash.length >= 8) ? file_hash.substring(0, 8) + "…" : "—"
                                    color: "#94a3b8"; font.pixelSize: 11; font.family: "Monospace"
                                    width: 120; anchors.verticalCenter: parent.verticalCenter
                                    ToolTip.visible: hashHov.hovered && file_hash !== ""
                                    ToolTip.text: file_hash
                                    HoverHandler { id: hashHov }
                                }

                                // Action buttons — visible on hover
                                Row {
                                    width: 130; spacing: 4; anchors.verticalCenter: parent.verticalCenter
                                    visible: rowHov.containsMouse

                                    // ── TRASH VIEW: Restore + Delete Forever ──
                                    Rectangle {
                                        visible: currentView === "trash"
                                        width: 32; height: 32; radius: 16
                                        color: restHov.containsMouse ? "#e6f4ea" : "transparent"
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        HoverHandler { id: restHov }
                                        Text { anchors.centerIn: parent; text: "↩"; color: "#1e8e3e"; font.pixelSize: 16; font.bold: true }
                                        MouseArea { anchors.fill: parent; onClicked: backend.restoreFile(name) }
                                        ToolTip.visible: restHov.hovered; ToolTip.text: "Restore"
                                    }
                                    Rectangle {
                                        visible: currentView === "trash"
                                        width: 32; height: 32; radius: 16
                                        color: purgeHov.containsMouse ? "#fce8e6" : "transparent"
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        HoverHandler { id: purgeHov }
                                        Text { anchors.centerIn: parent; text: "✕"; color: "#d93025"; font.pixelSize: 14; font.bold: true }
                                        MouseArea { anchors.fill: parent; onClicked: backend.purgeFile(name) }
                                        ToolTip.visible: purgeHov.hovered; ToolTip.text: "Delete forever"
                                    }

                                    // ── NORMAL VIEW: Star + Info + Download + Delete ──
                                    Rectangle {
                                        visible: currentView !== "trash"
                                        width: 32; height: 32; radius: 16
                                        color: starHov.containsMouse ? "#fef9e7" : "transparent"
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        HoverHandler { id: starHov }
                                        Text { anchors.centerIn: parent; text: "⭐"; font.pixelSize: 14 }
                                        MouseArea { anchors.fill: parent; onClicked: backend.starFile(name) }
                                        ToolTip.visible: starHov.hovered; ToolTip.text: "Star"
                                    }

                                    // ── File Info (blockchain) button ──────────
                                    Rectangle {
                                        visible: currentView !== "trash" && file_hash !== ""
                                        width: 32; height: 32; radius: 16
                                        color: infoHov.containsMouse ? "#e8f0fe" : "transparent"
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        HoverHandler { id: infoHov }
                                        Text { anchors.centerIn: parent; text: "ℹ"; color: "#1a73e8"; font.pixelSize: 15; font.bold: true }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: {
                                                // Pre-fill panel with what we already know
                                                fileInfoPanel.infoFilename  = name
                                                fileInfoPanel.infoFileHash  = file_hash
                                                fileInfoPanel.infoFileSize  = size
                                                fileInfoPanel.infoOwner     = loggedInUser
                                                fileInfoPanel.infoTimestamp = modified
                                                fileInfoPanel.infoHistory   = []
                                                fileInfoPanel.visible       = true
                                                // Fetch full metadata + history from blockchain
                                                backend.getFileDetails(file_hash)
                                                backend.getFileHistory(file_hash)
                                            }
                                        }
                                        ToolTip.visible: infoHov.hovered; ToolTip.text: "File Info (blockchain)"
                                    }

                                    Rectangle {
										visible: currentView !== "trash"
										width: 32; height: 32; radius: 16
										color: dlHov.containsMouse ? "#e8f0fe" : "transparent"
										Behavior on color { ColorAnimation { duration: 80 } }
										HoverHandler { id: dlHov }
										
										Text { 
											anchors.centerIn: parent; 
											text: "↓"; 
											color: "#1a73e8"; 
											font.pixelSize: 16; 
											font.bold: true 
										}
										
										MouseArea {
											anchors.fill: parent
											onClicked: { 
												// 1. עדכון ויזואלי למשתמש
												statusBar.text = "Downloading " + name + "..."; 
												statusBar.color = "#1a73e8";
												
												// 2. הפעלה של הפונקציה ב-Python (זה החלק שהיה חסר!)
												backend.downloadFile(name, "downloads"); 
											}
										}
										
										ToolTip.visible: dlHov.hovered; 
										ToolTip.text: "Download"
									}
                                    Rectangle {
                                        visible: currentView !== "trash"
                                        width: 32; height: 32; radius: 16
                                        color: delHov.containsMouse ? "#fce8e6" : "transparent"
                                        Behavior on color { ColorAnimation { duration: 80 } }
                                        HoverHandler { id: delHov }
                                        Text { anchors.centerIn: parent; text: "🗑"; font.pixelSize: 14 }
                                        MouseArea { anchors.fill: parent; onClicked: backend.deleteFile(name) }
                                        ToolTip.visible: delHov.hovered; ToolTip.text: "Move to Trash"
                                    }
                                }
                            }
                        }

                        // Empty state
                        Item {
                            anchors.centerIn: parent; width: 300; height: 200
                            visible: fileListView.count === 0
                            Column {
                                anchors.centerIn: parent; spacing: 12
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: currentView === "trash" ? "🗑" : currentView === "starred" ? "⭐" : "📂"
                                    font.pixelSize: 48
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: {
                                        if (currentView === "trash")   return "Trash is empty"
                                        if (currentView === "starred") return "No starred files"
                                        if (currentView === "recent")  return "No recent files"
                                        return "No files yet"
                                    }
                                    color: "#202124"; font.pixelSize: 16; font.bold: true
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: {
                                        if (currentView === "trash")   return "Files you delete will appear here"
                                        if (currentView === "starred") return "Star files to find them quickly"
                                        return "Click Upload or use the New button"
                                    }
                                    color: "#5f6368"; font.pixelSize: 13
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}



