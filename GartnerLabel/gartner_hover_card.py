"""
gartner_hover_card.py  -  Gartner Hover Card
============================================
Rest the mouse on a node in Nuke's Node Graph and a small card shows what
you need to know about it - without opening anything:

  * warnings first      errors, missing file on this frame, disabled
  * per node type       Read: colorspace, range on disk, file
                        Write: output, folder, type, colorspace
                        Merge: operation, which nodes feed A and B
                        Group / gizmo: nodes inside, gizmo file
  * image info          resolution, frames, layers, bbox (when bigger than
                        the format), premult, cook time (when profiling is on),
                        how many nodes depend on it
  * CHANGED             every knob you changed from its default, with value
  * pipes               rest on a pipe: from -> to, which input (A, B, mask)
  * backdrops           rest on the title strip: label + nodes inside

Nothing in the script is changed. Standalone, shareable: one file.

Install
-------
Put this file in a folder on your NUKE_PATH (e.g. ~/.nuke) and add one line
to the menu.py in that folder:

    import gartner_hover_card

Menu: Gartner > Hover Card On - Off. Tested with Nuke 16 (PySide6).
"""

import html
import os
import sys
import time

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

try:
    import nuke
except ImportError:
    nuke = None

# make "import gartner_hover_card" work however this file was loaded
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.append(_HERE)
except NameError:
    pass
if (__name__ != "gartner_hover_card" and "gartner_hover_card" not in sys.modules
        and sys.modules.get(__name__) is not None):
    sys.modules["gartner_hover_card"] = sys.modules[__name__]


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
class Settings(object):
    enabled = True
    delay = 0.5               # seconds the mouse rests on a node before the card
    accent = "#f5c518"        # card accent (left bar, section titles)
    color_drag = "#ff8c1a"    # warnings like "bbox bigger than format"
    color_pan = "#4fc3f7"     # animated / expression values
    card_max_changed = 8      # how many changed knobs to list
    pipe_info = True          # cards for pipes too
    view_scale = 1.0          # only change if the card picks the wrong node


SETTINGS = Settings()


# --------------------------------------------------------------------------- #
# Node Graph geometry (Nuke 16 draws the graph in an embedded native window)
# --------------------------------------------------------------------------- #
def _root_dag():
    for w in QtWidgets.QApplication.instance().allWidgets():
        if w.objectName() == "DAG.1":
            return w
    return None


def _view_widget(dag):
    """The part of the panel that actually shows the graph. In Nuke 16 that's
    a QWindowContainer holding a native window (not the whole panel, which
    also has the tab/toolbar area)."""
    best, area = None, 0
    for c in dag.findChildren(QtWidgets.QWidget):
        if c.metaObject().className() == "QWindowContainer" and c.isVisible():
            a = c.width() * c.height()
            if a > area:
                best, area = c, a
    return best or dag



def _graph_point(dag, gpos):
    """Screen position -> Node Graph coordinates."""
    view = _view_widget(dag)
    local = view.mapFromGlobal(gpos)
    z = nuke.zoom() * SETTINGS.view_scale
    cx, cy = nuke.center()
    x = cx + (local.x() - view.width() / 2.0) / z
    y = cy + (local.y() - view.height() / 2.0) / z
    return x, y



_reported = set()


def _report(where, exc):
    """Print each distinct error once instead of hiding it."""
    msg = "%s: %s" % (where, exc)
    if msg not in _reported:
        _reported.add(msg)
        print("gartner_hover_card error | %s" % msg)



# --------------------------------------------------------------------------- #
# The card
# --------------------------------------------------------------------------- #
class _InfoCard(QtWidgets.QWidget):
    def __init__(self):
        flags = (QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint
                 | QtCore.Qt.WindowStaysOnTopHint)
        super(_InfoCard, self).__init__(None, flags)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName("card")
        inner = QtWidgets.QVBoxLayout(self.frame)
        inner.setContentsMargins(12, 9, 14, 10)
        self.label = QtWidgets.QLabel()
        self.label.setTextFormat(QtCore.Qt.RichText)
        inner.addWidget(self.label)
        lay.addWidget(self.frame)
        self.restyle()

    def restyle(self):
        self.frame.setStyleSheet(
            "#card { background: rgba(22, 23, 25, 240);"
            " border: 1px solid #36383c; border-left: 3px solid %s;"
            " border-radius: 6px; }"
            "QLabel { color: #d9d9d9; font-size: 11px; background: transparent; }"
            % SETTINGS.accent)

    def show_for(self, node, gpos):
        if isinstance(node, tuple):                # ("pipe", src, dst, index)
            self.label.setText(_pipe_html(*node[1:]))
        else:
            self.label.setText(_card_html(node))
        self.adjustSize()
        self._place(gpos)
        self.show()

    def _place(self, gpos):
        pos = gpos + QtCore.QPoint(20, 22)
        screen = QtGui.QGuiApplication.screenAt(gpos)
        if screen is not None:                     # keep it on screen
            area = screen.availableGeometry()
            if pos.x() + self.width() > area.right():
                pos.setX(gpos.x() - self.width() - 12)
            if pos.y() + self.height() > area.bottom():
                pos.setY(gpos.y() - self.height() - 12)
        self.move(pos)


# knobs that are UI / bookkeeping, never interesting in "Changed"
_SKIP_KNOBS = {
    "xpos", "ypos", "selected", "name", "tile_color", "gl_color", "label",
    "note_font", "note_font_size", "note_font_color", "hide_input",
    "postage_stamp", "postage_stamp_frame", "cached", "indicators",
    "dope_sheet", "bookmark", "help", "onCreate", "onDestroy", "knobChanged",
    "updateUI", "autolabel", "panel", "lifetimeStart", "lifetimeEnd",
    "useLifetime", "icon", "window", "disable", "file", "proxy", "selectable",
    "process_mask", "z_order", "bdwidth", "bdheight", "appearance", "border_width",
}
_SKIP_CLASSES = {"Tab_Knob", "Text_Knob", "Obsolete_Knob", "PyScript_Knob",
                 "Help_Knob", "Link_Knob", "PyCustom_Knob", "Script_Knob"}

GREY = "#85888d"
RED = "#ff6b6b"


def _short(text, limit=44):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit // 2 - 1] + "…" + text[-(limit // 2 - 1):]


def _knob_value(k):
    try:
        if k.isAnimated():
            return "<span style='color:%s'>animated</span>" % SETTINGS.color_pan
    except Exception:
        pass
    try:
        if k.hasExpression():
            return "<span style='color:%s'>expression</span>" % SETTINGS.color_pan
    except Exception:
        pass
    try:
        v = k.toScript()
    except Exception:
        v = k.value()
    v = str(v).strip().strip("{}").strip()
    return html.escape(_short(v, 28))


def _changed_knobs(n):
    out = []
    for name, k in n.knobs().items():
        if name in _SKIP_KNOBS or name.startswith(("gl_", "_")):
            continue
        try:
            if k.Class() in _SKIP_CLASSES or not k.notDefault():
                continue
        except Exception:
            continue
        out.append((name, _knob_value(k)))
    return out


def _warnings(n):
    w = []
    try:
        if n.hasError():
            w.append("Node has an error")
    except Exception:
        pass
    if n.Class() in ("Read", "DeepRead") and "file" in n.knobs():
        try:
            path = n["file"].evaluate()
            if path and not os.path.exists(path):
                w.append("Missing file on frame %d" % nuke.frame())
        except Exception:
            pass
    try:
        if n["disable"].value():
            w.append("Disabled")
    except Exception:
        pass
    return w


def _type_rows(n, row):
    """A few rows that matter for this kind of node."""
    e = html.escape
    cls = n.Class()
    knobs = n.knobs()

    def val(name):
        return knobs[name].value() if name in knobs else None

    if cls in ("Read", "DeepRead"):
        if val("colorspace") is not None:
            row("Colorspace", e(str(val("colorspace"))))
        if val("first") is not None and val("last") is not None:
            row("On disk", "%d &ndash; %d" % (val("first"), val("last")))
        if val("file"):
            row("File", e(_short(os.path.basename(val("file")))))
    elif cls in ("Write", "DeepWrite"):
        path = val("file") or ""
        if path:
            row("Output", e(_short(os.path.basename(path))))
            row("Folder", "<span style='color:%s'>%s</span>"
                % (GREY, e(_short(os.path.dirname(path), 48))))
        if val("file_type"):
            row("Type", e(str(val("file_type"))))
        if val("colorspace") is not None:
            row("Colorspace", e(str(val("colorspace"))))
    elif cls.startswith("Merge"):
        if val("operation"):
            row("Operation", "<b>%s</b>" % e(str(val("operation"))))
        a, b = n.input(1), n.input(0)
        row("A", e(a.name()) if a else "<span style='color:%s'>&ndash;</span>" % GREY)
        row("B", e(b.name()) if b else "<span style='color:%s'>&ndash;</span>" % GREY)
    elif isinstance(n, nuke.Group):
        try:
            row("Inside", "%d nodes" % len(n.nodes()))
        except Exception:
            pass
        try:
            f = n.filename()
            if f:
                row("Gizmo", e(_short(os.path.basename(f))))
        except Exception:
            pass


def _backdrop_html(n):
    e = html.escape
    label = (n["label"].value() or "").strip()
    try:
        count = len(n.getNodes())
    except Exception:
        count = None
    head = ("<span style='font-size:13px; font-weight:600; color:#f2f2f2'>%s</span>"
            "&nbsp;&nbsp;<span style='color:%s'>Backdrop</span>"
            % (e(_short(label.splitlines()[0] if label else n.name(), 40)), GREY))
    rows = ""
    if count is not None:
        rows += ("<tr><td style='color:%s; padding:1px 14px 1px 0'>Contains</td>"
                 "<td>%d nodes</td></tr>" % (GREY, count))
    return "%s<table style='margin-top:6px'>%s</table>" % (head, rows)


def _card_html(n):
    if n.Class() == "BackdropNode":
        return _backdrop_html(n)

    e = html.escape
    rows = []

    def row(label, value, color=None):
        rows.append(
            "<tr><td style='color:%s; padding:1px 14px 1px 0'>%s</td>"
            "<td style='padding:1px 0%s'>%s</td></tr>"
            % (color or GREY, label, "; color:%s" % color if color else "", value))

    def section(title):
        rows.append("<tr><td colspan='2' style='padding:7px 0 2px 0; color:%s;"
                    " font-size:10px; letter-spacing:1px'>%s</td></tr>"
                    % (SETTINGS.accent, title))

    head = ("<span style='font-size:13px; font-weight:600; color:#f2f2f2'>%s</span>"
            "&nbsp;&nbsp;<span style='color:%s'>%s</span>" % (e(n.name()), GREY, e(n.Class())))

    # 1. warnings first
    for w in _warnings(n):
        row("&#9888;", "<b>%s</b>" % e(w), RED)

    # 2. what matters for this node type
    _type_rows(n, row)

    # 3. image info
    try:
        res = "%d &times; %d" % (n.width(), n.height())
        fmt = n.format().name()
        if fmt:
            res += "&nbsp;&nbsp;<span style='color:%s'>%s</span>" % (GREY, e(fmt))
        row("Resolution", res)
    except Exception:
        pass
    try:
        first, last = n.firstFrame(), n.lastFrame()
        row("Frames", "%d &ndash; %d&nbsp;&nbsp;<span style='color:%s'>(%d)</span>"
            % (first, last, GREY, last - first + 1))
    except Exception:
        pass
    try:
        bb = n.bbox()
        fw, fh = n.width(), n.height()
        if bb.x() < 0 or bb.y() < 0 or bb.x() + bb.w() > fw or bb.y() + bb.h() > fh:
            row("BBox", "%d &times; %d&nbsp;&nbsp;bigger than format"
                % (bb.w(), bb.h()), SETTINGS.color_drag)
    except Exception:
        pass
    try:
        chans = n.channels()
        layers = []
        for c in chans:
            layer = c.split(".")[0]
            if layer not in layers:
                layers.append(layer)
        shown = ", ".join(layers[:5])
        if len(layers) > 5:
            shown += "&nbsp;<span style='color:%s'>+%d</span>" % (GREY, len(layers) - 5)
        row("Layers", "%s&nbsp;&nbsp;<span style='color:%s'>%d ch</span>"
            % (shown, GREY, len(chans)))
    except Exception:
        pass
    if "premultiplied" in n.knobs():
        try:
            row("Premult", "yes" if n["premultiplied"].value() else "no")
        except Exception:
            pass
    try:
        if nuke.usingPerformanceTimers():
            info = n.performanceInfo()
            row("Cook", "%.1f ms" % (info.get("timeTakenWall", 0) / 1000.0), SETTINGS.accent)
    except Exception:
        pass
    try:
        row("Downstream", "%d nodes" % _downstream_count(n))
    except Exception:
        pass

    # 4. what you changed on this node
    try:
        changed = _changed_knobs(n)
        if n.Class().startswith("Merge"):
            changed = [c for c in changed if c[0] != "operation"]   # shown above
        if changed:
            section("CHANGED")
            for name, value in changed[:SETTINGS.card_max_changed]:
                row(e(name), value)
            if len(changed) > SETTINGS.card_max_changed:
                row("", "<span style='color:%s'>+%d more</span>"
                    % (GREY, len(changed) - SETTINGS.card_max_changed))
    except Exception:
        pass

    return "%s<table style='margin-top:6px'>%s</table>" % (head, "".join(rows))


def _downstream_count(node, limit=5000):
    mask = nuke.INPUTS | nuke.HIDDEN_INPUTS
    seen, stack = set(), [node]
    while stack and len(seen) < limit:
        for d in stack.pop().dependent(mask, forceEvaluate=False):
            name = d.fullName()
            if name not in seen:
                seen.add(name)
                stack.append(d)
    return len(seen)



# pipes
def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _pipe_at(x, y, tolerance):
    """Closest visible pipe to (x, y) in graph units, as ("pipe", src, dst, i)."""
    best, best_d = None, tolerance
    for dst in nuke.allNodes():
        if dst.Class() == "BackdropNode":
            continue
        try:
            if "hide_input" in dst.knobs() and dst["hide_input"].value():
                continue
            n_in = dst.inputs()
        except Exception:
            continue
        bx = dst.xpos() + dst.screenWidth() / 2.0
        by = dst.ypos() + dst.screenHeight() / 2.0
        for i in range(n_in):
            src = dst.input(i)
            if src is None:
                continue
            ax = src.xpos() + src.screenWidth() / 2.0
            ay = src.ypos() + src.screenHeight() / 2.0
            d = _seg_dist(x, y, ax, ay, bx, by)
            if d < best_d:
                best, best_d = ("pipe", src, dst, i), d
    return best


def _input_name(node, i):
    if node.Class().startswith("Merge") or node.Class() in ("Copy", "Keymix", "Dissolve"):
        if i == 0:
            return "B"
        if i == 1:
            return "A"
    try:
        if node.optionalInput() == i:
            return "mask"
    except Exception:
        pass
    return "input %d" % (i + 1)


def _pipe_html(src, dst, i):
    e = html.escape
    head = ("<span style='font-size:13px; font-weight:600; color:#f2f2f2'>%s</span>"
            "&nbsp;<span style='color:%s'>&rarr;</span>&nbsp;"
            "<span style='font-size:13px; font-weight:600; color:#f2f2f2'>%s</span>"
            % (e(src.name()), SETTINGS.accent, e(dst.name())))
    rows = []

    def row(label, value):
        rows.append("<tr><td style='color:%s; padding:1px 14px 1px 0'>%s</td>"
                    "<td style='padding:1px 0'>%s</td></tr>" % (GREY, label, value))

    row("Input", "<b>%s</b>" % e(_input_name(dst, i)))
    try:
        row("Resolution", "%d &times; %d" % (src.width(), src.height()))
    except Exception:
        pass
    try:
        chans = src.channels()
        layers = []
        for c in chans:
            layer = c.split(".")[0]
            if layer not in layers:
                layers.append(layer)
        row("Layers", "%s&nbsp;&nbsp;<span style='color:%s'>%d ch</span>"
            % (e(", ".join(layers[:5])), GREY, len(chans)))
    except Exception:
        pass
    return "%s<table style='margin-top:6px'>%s</table>" % (head, "".join(rows))



# --------------------------------------------------------------------------- #
# Controller: one light timer
# --------------------------------------------------------------------------- #
class _Controller(QtCore.QObject):
    TICK_MS = 100

    def __init__(self, parent=None):
        super(_Controller, self).__init__(parent)
        self.card = _InfoCard()
        self._name = None
        self._target = None
        self._since = 0.0
        self._last_pos = None
        self._dag = None
        self._found_at = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self.TICK_MS)

    def stop(self):
        self._timer.stop()
        self.card.hide()

    def _graph(self):
        now = time.time()
        try:
            if self._dag is not None:
                self._dag.isVisible()
        except RuntimeError:
            self._dag = None
        if self._dag is None or now - self._found_at > 2.0:
            self._dag = _root_dag()
            self._found_at = now
        return self._dag

    def _tick(self):
        try:
            self._update()
        except Exception as exc:
            _report("tick", exc)

    def _update(self):
        if not SETTINGS.enabled:
            self.card.hide()
            return
        dag = self._graph()
        if dag is None or not dag.isVisible():
            self.card.hide()
            return
        app = QtWidgets.QApplication
        gpos = QtGui.QCursor.pos()
        under = app.widgetAt(gpos)
        inside = under is not None and (under is dag or dag.isAncestorOf(under))
        if not inside or app.mouseButtons() != QtCore.Qt.NoButton:
            self._name = None
            self.card.hide()
            return

        now = time.time()
        if gpos != self._last_pos:
            self._last_pos = QtCore.QPoint(gpos)
            hit = _thing_at(dag, gpos)
            if isinstance(hit, tuple):
                name = "pipe:%s>%s:%d" % (hit[1].fullName(), hit[2].fullName(), hit[3])
            else:
                name = hit.fullName() if hit is not None else None
            if name != self._name:
                self._name, self._target, self._since = name, hit, now
                self.card.hide()
            elif self.card.isVisible():
                self.card._place(gpos)

        if self._name and not self.card.isVisible() and now - self._since >= SETTINGS.delay:
            try:
                self.card.show_for(self._target, gpos)
            except Exception as exc:
                _report("card", exc)
                self._name = None


def _thing_at(dag, gpos):
    """Node, backdrop title strip, or pipe under the cursor."""
    x, y = _graph_point(dag, gpos)
    hit, backdrop = None, None
    for n in nuke.allNodes():
        inside_x = n.xpos() <= x <= n.xpos() + n.screenWidth()
        if n.Class() == "BackdropNode":
            if inside_x and n.ypos() <= y <= n.ypos() + 40:
                backdrop = n
            continue
        if inside_x and n.ypos() <= y <= n.ypos() + n.screenHeight():
            hit = n
    if hit is None and SETTINGS.pipe_info:
        pipe = _pipe_at(x, y, 6.0 / max(nuke.zoom(), 0.05))
        if pipe is not None:
            return pipe
    return hit or backdrop


# --------------------------------------------------------------------------- #
# Menu + install
# --------------------------------------------------------------------------- #
def toggle():
    SETTINGS.enabled = not SETTINGS.enabled
    print("Gartner Hover Card: %s" % ("ON" if SETTINGS.enabled else "OFF"))


_controller = None
_menu_added = False
_APP_FLAG = "gartner_hover_card_active"


def install():
    global _controller
    if nuke is None or not nuke.GUI:
        return
    app = QtWidgets.QApplication.instance()
    if _controller is None and app is not None:
        if app.property(_APP_FLAG):
            return                         # another copy is already running
        app.setProperty(_APP_FLAG, True)
        _controller = _Controller(app)
    _ensure_menu()


def uninstall():
    global _controller
    if _controller is not None:
        _controller.stop()
        _controller.deleteLater()
        _controller = None
        QtWidgets.QApplication.instance().setProperty(_APP_FLAG, False)


def _ensure_menu(tries=20):
    global _menu_added
    if _menu_added:
        return
    try:
        bar = nuke.menu("Nuke")
        if bar is None:
            raise RuntimeError("menu bar not ready")
        bar.addMenu("Gartner").addCommand(
            "Hover Card On - Off", "import gartner_hover_card; gartner_hover_card.toggle()")
        _menu_added = True
    except Exception:
        if tries > 0:
            QtCore.QTimer.singleShot(500, lambda: _ensure_menu(tries - 1))


try:
    install()
except Exception as _exc:
    print("gartner_hover_card: auto-install failed: %s" % _exc)
