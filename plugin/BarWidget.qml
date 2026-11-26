import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs.Ui
import qs.Commons

// The bar shows one quiet cue (lemma for word mode, blanked cloze or English
// cue for Level 2 rungs so the bar does not spoil the answer). The command owns
// the day plan, the log, and the schedule.
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
  property string promptSentence: ""
  property bool refreshQueued: false
  property string job: ""
  property string queuedKind: ""
  property string queuedRating: ""
  property string jobOut: ""
  property string jobErr: ""

  readonly property string mode: card && card.mode ? String(card.mode) : ""
  readonly property string promptMode: card && card.promptMode ? String(card.promptMode) : "word"
  readonly property string lemma: card && card.word && card.word.lemma ? String(card.word.lemma) : ""
  readonly property string barLabel: {
    if (!lemma) return ""
    if (mode === "review" && card.revealed !== true) {
      if (promptMode === "cloze" && card.cloze) return String(card.cloze)
      if (promptMode === "reverse" && card.word && card.word.gloss) return String(card.word.gloss)
    }
    return lemma
  }
  readonly property bool hasWord: lemma !== ""
  readonly property bool resting: mode === "rest"
  readonly property string tooltip: {
    if (mode === "new") return "New today"
    if (mode === "review") {
      if (promptMode === "cloze") return "Sentence cloze"
      if (promptMode === "reverse") return "Recall Bahasa Melayu"
      return "Review"
    }
    if (mode === "rest") return "Resting"
    return ""
  }
  readonly property string faceMode: face && face.mode ? String(face.mode) : ""
  readonly property string facePromptMode: face && face.promptMode ? String(face.promptMode) : "word"
  readonly property string faceLemma: face && face.lemma ? String(face.lemma) : ""
  readonly property string faceRegister: face && face.register ? String(face.register) : "neutral"
  readonly property string faceGloss: face && face.gloss ? String(face.gloss) : ""
  readonly property string faceSentence: face && face.sentence ? String(face.sentence) : ""
  readonly property string faceSentenceGloss: face && face.sentenceGloss ? String(face.sentenceGloss) : ""
  readonly property string faceNote: face && face.note ? String(face.note) : ""
  readonly property var faceCousins: face && face.cousins ? face.cousins : []
  readonly property int faceRung: face && typeof face.intervalIndex === "number" ? face.intervalIndex : 0
  readonly property int faceLadder: face && typeof face.ladderLength === "number" ? face.ladderLength : 5
  readonly property string faceCounter: face && face.counter ? String(face.counter) : ""
  readonly property string rungDots: {
    var out = ""
    for (var i = 0; i < faceLadder; i++) {
      out += (i < faceRung ? "●" : "○")
      if (i + 1 < faceLadder) out += " "
    }
    return out
  }
  readonly property string cousinsCaption: faceCousins.length > 0 ? "cousins: " + faceCousins.join(", ") : ""
  readonly property var activeWorkspace: {
    var monitor = Hyprland.focusedMonitor
    return monitor && monitor.activeWorkspace ? monitor.activeWorkspace : null
  }
  readonly property string workspaceHint: activeWorkspace && activeWorkspace.name ? String(activeWorkspace.name) : ""
  readonly property bool showRatings: faceMode === "review" && !rated
  readonly property string caption: {
    if (rated && rateNote) return rateNote
    if (statusLine) return statusLine
    if (faceMode === "new") return "New today"
    if (faceMode === "review") {
      if (facePromptMode === "cloze") return "Sentence cloze"
      if (facePromptMode === "reverse") return "Recall Malay"
      return "Review"
    }
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
    promptSentence = ""
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
    requestPrompt()
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

  function requestPrompt() {
    request("prompt", "")
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
    else if (kind === "prompt") {
      command.push("prompt", "--json")
      if (root.workspaceHint !== "") command.push("--about", root.workspaceHint)
    }
    else command.push(kind, "--json")
    tepiProc.command = command
    tepiProc.running = true
  }

  function counterFor(payload) {
    if (!payload || !payload.plan || !payload.remaining) return ""
    var total = (payload.plan.reviews ? payload.plan.reviews.length : 0) + (payload.plan.new ? payload.plan.new.length : 0)
    if (total <= 0) return ""
    var left = (payload.remaining.reviews || 0) + (payload.remaining.new || 0)
    var done = Math.max(0, total - left)
    var cur = payload.mode === "rest" ? total : Math.min(done + 1, total)
    return cur + "/" + total
  }

  function faceFrom(payload) {
    var word = payload && payload.word ? payload.word : null
    if (!word || !word.lemma) return null
    return {
      lemma: String(word.lemma),
      register: word.register ? String(word.register) : "neutral",
      gloss: word.gloss ? String(word.gloss) : "",
      sentence: word.sentence ? String(word.sentence) : "",
      sentenceGloss: word.sentenceGloss ? String(word.sentenceGloss) : "",
      note: word.note ? String(word.note) : "",
      cousins: word.cousins ? word.cousins.map(String) : [],
      mode: String(payload.mode || ""),
      promptMode: payload.promptMode ? String(payload.promptMode) : "word",
      intervalIndex: typeof payload.intervalIndex === "number" ? payload.intervalIndex : 0,
      ladderLength: typeof payload.ladderLength === "number" ? payload.ladderLength : 5,
      counter: counterFor(payload)
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
    if (kind === "prompt") {
      promptSentence = payload.sentence ? String(payload.sentence) : ""
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
        promptSentence = ""
        popupOpen = true
        requestPrompt()
      }
      return
    }
    if (kind === "rate") {
      rated = true
      rateNote = payload.state === "settled" ? "Settled" : (payload.due ? ("Due " + payload.due) : "Recorded")
      if (payload.word) {
        face = {
          lemma: String(payload.word.lemma || faceLemma),
          register: payload.word.register ? String(payload.word.register) : faceRegister,
          gloss: payload.word.gloss ? String(payload.word.gloss) : "",
          sentence: payload.word.sentence ? String(payload.word.sentence) : "",
          sentenceGloss: payload.word.sentenceGloss ? String(payload.word.sentenceGloss) : "",
          note: payload.word.note ? String(payload.word.note) : "",
          cousins: payload.word.cousins ? payload.word.cousins.map(String) : [],
          mode: "review",
          promptMode: facePromptMode,
          intervalIndex: typeof payload.intervalIndex === "number" ? payload.intervalIndex : faceRung,
          ladderLength: faceLadder,
          counter: faceCounter
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

  Process {
    id: webProc
    command: [root.tepiBin, "web"]
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
    text: root.barLabel
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
    contentWidth: popup.fittedContentWidth(Style.space(320))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    Column {
      id: column
      width: parent.width
      spacing: Style.space(8)
      focus: root.popupOpen

      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) {
          root.dismiss()
          event.accepted = true
        } else if (root.showRatings && event.key === Qt.Key_1) {
          root.rate("known")
          event.accepted = true
        } else if (root.showRatings && event.key === Qt.Key_2) {
          root.rate("fuzzy")
          event.accepted = true
        } else if (root.showRatings && event.key === Qt.Key_3) {
          root.rate("missed")
          event.accepted = true
        }
      }

      Row {
        width: column.width
        spacing: Style.space(8)

        Text {
          textFormat: Text.PlainText
          text: root.caption + (root.faceCounter ? ("  ·  " + root.faceCounter) : "")
          color: Qt.darker(root.popupInk, 1.55)
          font.family: root.inkFont
          font.pixelSize: Style.font.caption
        }

        Item { width: Style.space(4); height: 1 }

        Text {
          textFormat: Text.PlainText
          text: root.rungDots
          color: Qt.darker(root.popupInk, 1.35)
          font.family: root.inkFont
          font.pixelSize: Style.font.caption
        }
      }

      Row {
        width: column.width
        spacing: Style.space(6)

        Text {
          textFormat: Text.PlainText
          text: root.faceLemma
          color: root.popupInk
          font.family: root.inkFont
          font.pixelSize: Style.font.subtitle
          font.bold: true
        }

        Text {
          visible: root.faceRegister !== "neutral"
          anchors.baseline: parent.children[0].baseline
          textFormat: Text.PlainText
          text: "(" + root.faceRegister + ")"
          color: Qt.darker(root.popupInk, 1.5)
          font.family: root.inkFont
          font.pixelSize: Style.font.caption
        }
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
        color: Qt.darker(root.popupInk, 1.25)
        font.family: root.inkFont
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.faceSentenceGloss
        color: Qt.darker(root.popupInk, 1.5)
        font.family: root.inkFont
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.faceNote
        color: Qt.darker(root.popupInk, 1.55)
        font.family: root.inkFont
        font.pixelSize: Style.font.caption
        font.italic: true
        wrapMode: Text.WordWrap
      }

      Text {
        width: column.width
        visible: text !== ""
        textFormat: Text.PlainText
        text: root.promptSentence
        color: Qt.darker(root.popupInk, 1.45)
        font.family: root.inkFont
        font.pixelSize: Style.font.bodySmall
        font.italic: true
        wrapMode: Text.WordWrap
      }

      Row {
        visible: root.showRatings
        height: visible ? implicitHeight : 0
        spacing: Style.space(6)

        Button {
          text: "Known (1)"
          foreground: root.popupInk
          enabled: !root.ratingBusy
          opacity: enabled ? 1 : 0.4
          onClicked: root.rate("known")
        }
        Button {
          text: "Fuzzy (2)"
          foreground: root.popupInk
          enabled: !root.ratingBusy
          opacity: enabled ? 1 : 0.4
          onClicked: root.rate("fuzzy")
        }
        Button {
          text: "Missed (3)"
          foreground: root.popupInk
          enabled: !root.ratingBusy
          opacity: enabled ? 1 : 0.4
          onClicked: root.rate("missed")
        }
      }

      Button {
        text: "Open Web"
        foreground: root.popupInk
        enabled: !webProc.running
        opacity: enabled ? 1 : 0.4
        onClicked: {
          if (!webProc.running) webProc.running = true
        }
      }
    }
  }
}
