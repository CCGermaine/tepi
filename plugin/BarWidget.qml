import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

// The bar shows one lemma. The command owns the day plan, the log, and the
// schedule. A new word's next `today` is the following word, so while the
// popup is open the chip holds the card it already fetched.
BarWidget {
  id: root
  moduleName: "manny.tepi"

  readonly property string tepiBin: "/home/manny/.local/bin/tepi"
  readonly property color barInk: bar ? bar.barForeground : Color.foreground
  readonly property color popupInk: bar ? bar.foreground : Color.foreground
  readonly property string inkFont: bar && bar.fontFamily ? bar.fontFamily : Style.font.family

  property var card: null
  property var face: null
  property bool popupOpen: false
  property bool wantPopup: false
  property bool rated: false
  property bool ratingBusy: false
  property string rateNote: ""
  property string statusLine: ""
  property bool refreshQueued: false
  property string job: ""
  property string queuedKind: ""
  property string queuedRating: ""
  property string jobOut: ""
  property string jobErr: ""

  readonly property string mode: card && card.mode ? String(card.mode) : ""
  readonly property string lemma: card && card.word && card.word.lemma ? String(card.word.lemma) : ""
  readonly property bool hasWord: lemma !== ""
  readonly property bool resting: mode === "rest"
  readonly property string tooltip: {
    if (mode === "new") return "New today"
    if (mode === "review") return "Review"
    if (mode === "rest") return "Resting"
    return ""
  }
  readonly property string faceMode: face && face.mode ? String(face.mode) : ""
  readonly property string faceLemma: face && face.lemma ? String(face.lemma) : ""
  readonly property string faceGloss: face && face.gloss ? String(face.gloss) : ""
  readonly property string faceSentence: face && face.sentence ? String(face.sentence) : ""
  readonly property var faceCousins: face && face.cousins ? face.cousins : []
  readonly property string cousinsCaption: faceCousins.length > 0 ? "cousins: " + faceCousins.join(", ") : ""
  readonly property bool showRatings: faceMode === "review" && !rated
  readonly property string caption: {
    if (rated && rateNote) return rateNote
    if (statusLine) return statusLine
    if (faceMode === "new") return "New today"
    if (faceMode === "review") return "Review"
    if (faceMode === "rest") return "Resting"
    return ""
  }

  readonly property bool opened: popupOpen

  function open() { present() }
  function close() { dismiss() }
  function toggle() {
    if (popupOpen) dismiss()
    else if (!wantPopup) present()
  }

  function present() {
    if (!hasWord || popupOpen || wantPopup) return
    statusLine = ""
    rated = false
    rateNote = ""
    var needsReveal = (mode === "new" || mode === "review") && card.revealed !== true
    if (needsReveal) {
      wantPopup = true
      request("reveal", "")
      return
    }
    var next = faceFrom(card)
    if (!next) return
    face = next
    popupOpen = true
  }

  function dismiss() {
    wantPopup = false
    popupOpen = false
    refresh()
  }

  function rate(rating) {
    if (rated || ratingBusy || faceMode !== "review") return
    statusLine = ""
    request("rate", rating)
  }

  function refresh() {
    if (popupOpen || wantPopup) {
      refreshQueued = true
      return
    }
    refreshQueued = false
    request("today", "")
  }

  function request(kind, rating) {
    if (tepiProc.running) {
      if (kind === "today") {
        refreshQueued = true
        return
      }
      queuedKind = kind
      queuedRating = rating || ""
      return
    }
    start(kind, rating)
  }

  function start(kind, rating) {
    job = kind
    jobOut = ""
    jobErr = ""
    if (kind === "rate") ratingBusy = true
    var command = [tepiBin]
    if (kind === "rate") command.push("rate", rating, "--json")
    else command.push(kind, "--json")
    tepiProc.command = command
    tepiProc.running = true
  }

  function faceFrom(payload) {
    var word = payload && payload.word ? payload.word : null
    if (!word || !word.lemma) return null
    return {
      lemma: String(word.lemma),
      gloss: word.gloss ? String(word.gloss) : "",
      sentence: word.sentence ? String(word.sentence) : "",
      cousins: word.cousins ? word.cousins.map(String) : [],
      mode: String(payload.mode || "")
    }
  }

  function apply(exitCode) {
    var kind = job
    var text = jobOut
    var err = (jobErr || "").trim()
    jobOut = ""
    jobErr = ""
    ratingBusy = false
    var payload = null
    if (exitCode === 0 && text) {
      try {
        payload = JSON.parse(text)
      } catch (e) {
        payload = null
      }
    }
    if (!payload) {
      console.warn("tepi:", err || (kind + " failed"))
      if (kind === "reveal") wantPopup = false
      if (kind === "rate") statusLine = "That rating did not save."
      return
    }
    if (kind === "today") {
      if ((payload.word && payload.word.lemma) || payload.mode === "empty") card = payload
      return
    }
    if (kind === "reveal") {
      var revealed = faceFrom(payload)
      if (wantPopup && revealed) {
        face = revealed
        rated = false
        rateNote = ""
        popupOpen = true
      }
      return
    }
    if (kind === "rate") {
      rated = true
      rateNote = payload.state === "settled" ? "Settled" : (payload.due ? ("Due " + payload.due) : "Recorded")
      if (payload.word) {
        face = {
          lemma: String(payload.word.lemma || faceLemma),
          gloss: payload.word.gloss ? String(payload.word.gloss) : "",
          sentence: payload.word.sentence ? String(payload.word.sentence) : "",
          cousins: payload.word.cousins ? payload.word.cousins.map(String) : [],
          mode: "review"
        }
      }
    }
  }

  function finish(exitCode) {
    if (tepiProc.running) return
    apply(exitCode)
    pump()
  }

  function pump() {
    if (tepiProc.running) return
    if (queuedKind !== "") {
      var kind = queuedKind
      var rating = queuedRating
      queuedKind = ""
      queuedRating = ""
      start(kind, rating)
      return
    }
    if (refreshQueued && !popupOpen && !wantPopup) {
      refreshQueued = false
      start("today", "")
    }
  }

  Component.onCompleted: refresh()

  Timer {
    interval: 60000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Timer {
    id: stallTimer
    interval: 8000
    onTriggered: if (tepiProc.running) tepiProc.running = false
  }

  Process {
    id: tepiProc
    command: [root.tepiBin, "today", "--json"]
    onStarted: stallTimer.restart()
    onExited: function(exitCode) {
      stallTimer.stop()
      var code = exitCode
      Qt.callLater(function() { root.finish(code) })
    }
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.jobOut = text
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.jobErr = text
    }
  }

  IpcHandler {
    target: "manny.tepi"

    function refresh(): void { root.broadcast("refresh") }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
  }

  visible: hasWord
  implicitWidth: hasWord ? lemmaLabel.implicitWidth + Style.space(16) : 0
  implicitHeight: barSize

  Text {
    id: lemmaLabel
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: root.lemma
    color: root.resting ? Qt.darker(root.barInk, 1.45) : root.barInk
    font.family: root.inkFont
    font.pixelSize: Style.font.body

    Behavior on color {
      enabled: !root.bar || root.bar.foregroundAnimationEnabled
      ColorAnimation { duration: 160 }
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    focus: false
    cursorShape: root.hasWord ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: root.toggle()
    onEntered: if (root.bar && root.tooltip) root.bar.showTooltip(root, root.tooltip)
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    triggerMode: "click"
    contentWidth: popup.fittedContentWidth(Style.space(300))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    Column {
      id: column
      width: parent.width
      spacing: Style.space(8)

      Text {
        width: column.width
        textFormat: Text.PlainText
        text: root.faceLemma
        color: root.popupInk
        font.family: root.inkFont
        font.pixelSize: Style.font.subtitle
        font.bold: true
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.cousinsCaption
        color: Qt.darker(root.popupInk, 1.55)
        font.family: root.inkFont
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.faceGloss
        color: root.popupInk
        font.family: root.inkFont
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.faceSentence
        color: Qt.darker(root.popupInk, 1.35)
        font.family: root.inkFont
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.caption
        color: Qt.darker(root.popupInk, 1.55)
        font.family: root.inkFont
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Row {
        visible: root.showRatings
        height: visible ? implicitHeight : 0
        spacing: Style.space(6)

        Button {
          text: "Known"
          foreground: root.popupInk
          enabled: !root.ratingBusy
          opacity: enabled ? 1 : 0.4
          onClicked: root.rate("known")
        }
        Button {
          text: "Fuzzy"
          foreground: root.popupInk
          enabled: !root.ratingBusy
          opacity: enabled ? 1 : 0.4
          onClicked: root.rate("fuzzy")
        }
        Button {
          text: "Missed"
          foreground: root.popupInk
          enabled: !root.ratingBusy
          opacity: enabled ? 1 : 0.4
          onClicked: root.rate("missed")
        }
      }
    }
  }
}
