"""EditorB — research proposal block editor."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIntValidator,
    QKeySequence,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


FONT_FAMILY = "Yu Gothic UI, Meiryo UI, Segoe UI"
FONT_DEFAULT_PT = 11
FONT_MIN_PT = 7
FONT_MAX_PT = 28
FILE_EXT = ".editorb"
FILE_FILTER_NATIVE = "EditorB (*.editorb)"
EXPORT_FILTER = "Markdown (*.md);;Text (*.txt)"
EN_DASH = "\u2013"
RULE = "━" * 20
APP_NAME = "EditorB"
COLUMN_WIDTH_RATIO = 0.90


QSS = """
QMainWindow, QWidget#central, QScrollArea, QScrollArea > QWidget > QWidget {
    background: #1e1e1e;
    color: #d4d4d4;
}
QFrame#header {
    background: #252526;
    border-bottom: 1px solid #333;
}
QLineEdit#title {
    background: transparent;
    color: #e0e0e0;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}
QLineEdit#title:hover, QLineEdit#title:focus {
    background: #2d2d2d;
}
QPushButton#btn_add {
    background: transparent;
    color: #555;
    border: none;
    padding: 4px 10px;
}
QPushButton#btn_add:hover {
    color: #569cd6;
}

QFrame#block {
    background: #252526;
    border: 1px solid #333;
    border-radius: 6px;
}
QFrame#description_area {
    background: #2d2d2d;
    border: none;
    border-bottom: 1px solid #333;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QFrame#content_area {
    background: transparent;
    border: none;
}
QPlainTextEdit#description {
    background: #2d2d2d;
    color: #9a9a9a;
    border: none;
    selection-background-color: #264f78;
}
QPlainTextEdit#content {
    background: transparent;
    color: #e0e0e0;
    border: none;
    selection-background-color: #264f78;
}
QFrame#footer {
    background: #2a2a2a;
    border: none;
    border-top: 1px solid #333;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
}
QLabel#count {
    color: #888;
}
QLabel#count[over="true"] {
    color: #e0a050;
}
QLabel#slash, QLabel#unit {
    color: #666;
}
QCheckBox#check {
    color: #888;
    spacing: 5px;
}
QCheckBox#check::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #666;
    border-radius: 3px;
    background: transparent;
}
QCheckBox#check::indicator:hover {
    border-color: #888;
}
QCheckBox#check::indicator:checked {
    background: #3a5a73;
    border-color: #4a6f8a;
    image: none;
}
QCheckBox#check:checked {
    color: #b0b0b0;
}
QLineEdit#limit {
    background: transparent;
    color: #888;
    border: none;
    border-bottom: 1px solid #555;
    padding: 0 2px;
}
QLineEdit#limit:focus {
    border-bottom-color: #569cd6;
    color: #d4d4d4;
}

QFrame#statusbar {
    background: #1e1e1e;
    border-top: 1px solid #2a2a2a;
}
QFrame#statusbar QLabel {
    color: #666;
    background: transparent;
}

QScrollArea { border: none; }
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #444;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QMessageBox {
    background: #252526;
    color: #d4d4d4;
}
QMessageBox QLabel { color: #d4d4d4; }
QMessageBox QPushButton {
    background: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555;
    padding: 4px 14px;
    min-width: 70px;
    border-radius: 3px;
}
QMessageBox QPushButton:hover { background: #4a4a4a; }
QMessageBox QPushButton:default { background: #0e639c; border-color: #1177bb; }
"""


def _repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


class AutoResizingTextEdit(QPlainTextEdit):
    """QPlainTextEdit that grows to fit its content."""

    def __init__(
        self,
        min_lines: int,
        placeholder: str,
        object_name: str,
        placeholder_color: str = "#555",
    ) -> None:
        super().__init__()
        self._min_lines = min_lines
        self.setObjectName(object_name)
        self.setPlaceholderText(placeholder)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(placeholder_color))
        self.setPalette(pal)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        self.document().documentLayout().documentSizeChanged.connect(
            lambda _=None: self._adjust_height()
        )
        self._adjust_height()

    def setFont(self, font: QFont) -> None:  # noqa: N802
        super().setFont(font)
        self.viewport().setFont(font)
        self.document().setDefaultFont(font)
        self.viewport().update()
        self._adjust_height()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._adjust_height()

    def _adjust_height(self) -> None:
        doc = self.document()
        layout = doc.documentLayout()
        doc_h = 0.0
        block = doc.begin()
        while block.isValid():
            doc_h += layout.blockBoundingRect(block).height()
            block = block.next()
        fm = QFontMetrics(self.font())
        line_h = fm.lineSpacing()
        min_h = line_h * self._min_lines
        h = max(doc_h, min_h)
        margins = self.contentsMargins()
        frame = 2 * self.frameWidth()
        total = int(h) + margins.top() + margins.bottom() + frame + 4
        self.setFixedHeight(total)


class BlockWidget(QFrame):
    """A single block: description (gray), content (main), footer (counter)."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("block")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.description = AutoResizingTextEdit(
            min_lines=1,
            placeholder="項目の説明を入力...",
            object_name="description",
            placeholder_color="#555",
        )
        self.content = AutoResizingTextEdit(
            min_lines=6,
            placeholder="本文を入力...",
            object_name="content",
            placeholder_color="#444",
        )

        # description area wrapper (for padding via QSS)
        desc_area = QFrame()
        desc_area.setObjectName("description_area")
        desc_layout = QVBoxLayout(desc_area)
        desc_layout.setContentsMargins(16, 10, 16, 10)
        desc_layout.addWidget(self.description)

        content_area = QFrame()
        content_area.setObjectName("content_area")
        c_layout = QVBoxLayout(content_area)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.addWidget(self.content)

        # footer
        self.footer = QFrame()
        self.footer.setObjectName("footer")
        f_layout = QHBoxLayout(self.footer)
        f_layout.setContentsMargins(16, 8, 16, 8)
        f_layout.setSpacing(8)
        f_layout.addStretch(1)

        self.cb_show = QCheckBox("文字数")
        self.cb_show.setObjectName("check")
        self.cb_show.setChecked(False)

        self.lbl_count = QLabel("0")
        self.lbl_count.setObjectName("count")
        self.lbl_count.setProperty("over", False)

        self.lbl_slash = QLabel("/")
        self.lbl_slash.setObjectName("slash")

        self.ed_limit = QLineEdit()
        self.ed_limit.setObjectName("limit")
        self.ed_limit.setValidator(QIntValidator(0, 99999, self))
        self.ed_limit.setMaxLength(5)
        self.ed_limit.setFixedWidth(48)
        self.ed_limit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ed_limit.setPlaceholderText("—")

        self.lbl_unit = QLabel("文字")
        self.lbl_unit.setObjectName("unit")

        f_layout.addWidget(self.cb_show)
        f_layout.addWidget(self.lbl_count)
        f_layout.addWidget(self.lbl_slash)
        f_layout.addWidget(self.ed_limit)
        f_layout.addWidget(self.lbl_unit)

        # outer
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(desc_area)
        outer.addWidget(content_area)
        outer.addWidget(self.footer)

        # signals
        self.description.textChanged.connect(self._on_changed)
        self.content.textChanged.connect(self._on_content_changed)
        self.cb_show.toggled.connect(self._on_changed)
        self.ed_limit.textChanged.connect(self._on_changed)

        self._refresh_counter()

    def _on_content_changed(self) -> None:
        self._refresh_counter()
        self.changed.emit()

    def _on_changed(self, *_args) -> None:
        self._refresh_counter()
        self.changed.emit()

    def _refresh_counter(self) -> None:
        text = self.content.toPlainText()
        n = len(text.replace("\n", ""))
        try:
            limit = int(self.ed_limit.text() or "0")
        except ValueError:
            limit = 0

        if not self.cb_show.isChecked():
            self.lbl_count.hide()
            self.lbl_slash.hide()
            self.ed_limit.hide()
            self.lbl_unit.hide()
            return

        self.lbl_count.show()
        self.lbl_unit.show()
        self.ed_limit.show()
        self.lbl_count.setText(str(n))

        if limit > 0:
            self.lbl_slash.show()
            over = n > limit
        else:
            self.lbl_slash.hide()
            over = False

        if self.lbl_count.property("over") != over:
            self.lbl_count.setProperty("over", over)
            _repolish(self.lbl_count)

    def apply_font(self, ui_font: QFont, content_font: QFont) -> None:
        self.description.setFont(content_font)
        self.content.setFont(content_font)
        for w in (self.cb_show, self.lbl_count, self.lbl_slash, self.ed_limit, self.lbl_unit):
            w.setFont(ui_font)

    def to_dict(self) -> dict:
        try:
            limit = int(self.ed_limit.text() or "0")
        except ValueError:
            limit = 0
        return {
            "description": self.description.toPlainText(),
            "content": self.content.toPlainText(),
            "char_limit": max(0, limit),
            "show_count": self.cb_show.isChecked(),
        }

    def load_from_dict(self, d: dict) -> None:
        self.description.blockSignals(True)
        self.content.blockSignals(True)
        self.cb_show.blockSignals(True)
        self.ed_limit.blockSignals(True)
        try:
            self.description.setPlainText(str(d.get("description", "")))
            self.content.setPlainText(str(d.get("content", "")))
            try:
                limit = int(d.get("char_limit", 0))
            except (TypeError, ValueError):
                limit = 0
            limit = max(0, limit)
            self.ed_limit.setText(str(limit) if limit > 0 else "")
            self.cb_show.setChecked(bool(d.get("show_count", False)))
        finally:
            self.description.blockSignals(False)
            self.content.blockSignals(False)
            self.cb_show.blockSignals(False)
            self.ed_limit.blockSignals(False)
        self._refresh_counter()


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return cleaned or "untitled"


def _split_description(s: str) -> tuple[str, str]:
    lines = s.splitlines()
    head_idx = next((i for i, ln in enumerate(lines) if ln.rstrip()), -1)
    if head_idx < 0:
        return "", ""
    head = lines[head_idx].rstrip()
    rest_lines = lines[head_idx + 1:]
    while rest_lines and not rest_lines[0].strip():
        rest_lines.pop(0)
    rest = "\n".join(rest_lines).rstrip()
    return head, rest


def _validate_data(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("ファイル形式が正しくありません")
    if raw.get("version") != 1:
        raise ValueError(f"対応していないバージョンです: {raw.get('version')!r}")
    title = raw.get("title", "")
    if not isinstance(title, str):
        title = str(title)
    blocks_raw = raw.get("blocks", [])
    if not isinstance(blocks_raw, list):
        raise ValueError("blocks フィールドが配列ではありません")
    blocks = []
    for b in blocks_raw:
        if not isinstance(b, dict):
            continue
        try:
            limit = int(b.get("char_limit", 0))
        except (TypeError, ValueError):
            limit = 0
        blocks.append({
            "description": str(b.get("description", "")),
            "content": str(b.get("content", "")),
            "char_limit": max(0, limit),
            "show_count": bool(b.get("show_count", False)),
        })
    return {"version": 1, "title": title, "blocks": blocks}


def _export_markdown(data: dict) -> str:
    parts = []
    title = data.get("title", "").strip()
    if title:
        parts.append(f"# {title}")
        parts.append("")
    for b in data["blocks"]:
        # 出力は description / content だけから作られるので、両方空ならスキップ。
        if not b.get("description", "").strip() and not b.get("content", "").strip():
            continue
        head, rest = _split_description(b.get("description", ""))
        body = b.get("content", "").rstrip()
        if head:
            parts.append(f"## {head}")
            parts.append("")
        if rest:
            parts.append("\n".join(f"> {ln}" if ln else ">" for ln in rest.splitlines()))
            parts.append("")
        if body:
            parts.append(body)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _export_text(data: dict) -> str:
    parts = []
    title = data.get("title", "").strip()
    if title:
        parts.append(title)
        parts.append(RULE)
        parts.append("")
    for b in data["blocks"]:
        # 出力は description / content だけから作られるので、両方空ならスキップ。
        # （残すと罫線が2本連続する）
        if not b.get("description", "").strip() and not b.get("content", "").strip():
            continue
        head, rest = _split_description(b.get("description", ""))
        body = b.get("content", "").rstrip()
        if head:
            parts.append(f"【{head}】")
            parts.append("")
        if rest:
            parts.append("\n".join(f"│ {ln}" if ln else "│" for ln in rest.splitlines()))
            parts.append("")
        if body:
            parts.append(body)
            parts.append("")
        parts.append(RULE)
        parts.append("")
    while parts and parts[-1] in ("", RULE):
        parts.pop()
    return "\n".join(parts) + "\n"


class EditorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(900, 700)
        self.setMinimumSize(600, 400)

        self.blocks: list[BlockWidget] = []
        self.current_path: Optional[Path] = None
        self.dirty: bool = False
        self.base_pt: int = FONT_DEFAULT_PT
        self._loading: bool = False
        self._saved_snapshot: str = ""

        self._build_ui()
        self._build_shortcuts()
        self._apply_fonts()

        self.add_block(initial=True)
        self._saved_snapshot = self._snapshot()
        self.dirty = False
        self._update_status()
        self._update_window_title()
        if self.blocks:
            self.blocks[0].content.setFocus()

        QApplication.instance().installEventFilter(self)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        header = QFrame()
        header.setObjectName("header")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 12, 24, 12)
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("title")
        self.title_edit.setPlaceholderText("タイトルを入力...")
        pal = self.title_edit.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#666"))
        self.title_edit.setPalette(pal)
        self.title_edit.textChanged.connect(self._mark_dirty)
        self.btn_add = QPushButton("＋")
        self.btn_add.setObjectName("btn_add")
        self.btn_add.setToolTip("ブロック追加")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        # NOTE: clicked(bool) を位置引数で受けないよう lambda で吸収する。
        self.btn_add.clicked.connect(lambda _checked=False: self.add_block())
        h_layout.addWidget(self.title_edit, 1)
        h_layout.addWidget(self.btn_add, 0)
        root.addWidget(header)

        # scroll area with centered column
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        outer_h = QHBoxLayout(inner)
        outer_h.setContentsMargins(16, 24, 16, 24)
        outer_h.addStretch(1)
        self.column = QWidget()
        self.column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.scroll.viewport().installEventFilter(self)
        self.column_layout = QVBoxLayout(self.column)
        self.column_layout.setContentsMargins(0, 0, 0, 0)
        self.column_layout.setSpacing(20)
        self.column_layout.addStretch(1)
        outer_h.addWidget(self.column, 1)
        outer_h.addStretch(1)
        self.scroll.setWidget(inner)
        root.addWidget(self.scroll, 1)

        # status bar (custom)
        self.statusbar = QFrame()
        self.statusbar.setObjectName("statusbar")
        s_layout = QHBoxLayout(self.statusbar)
        s_layout.setContentsMargins(16, 4, 16, 4)
        self.lbl_status_left = QLabel("保存済み")
        self.lbl_status_right = QLabel("新規")
        s_layout.addWidget(self.lbl_status_left, 0)
        s_layout.addStretch(1)
        s_layout.addWidget(self.lbl_status_right, 0)
        root.addWidget(self.statusbar)

    def _build_shortcuts(self) -> None:
        sc = lambda seq, fn: QShortcut(QKeySequence(seq), self, activated=fn)  # noqa: E731
        sc("Ctrl+N", self.action_new)
        sc("Ctrl+O", self.action_open)
        sc("Ctrl+S", self.action_save)
        sc("Ctrl+Shift+S", self.action_save_as)
        sc("Ctrl+E", self.action_export)
        sc("Ctrl+0", self.action_zoom_reset)
        sc("Ctrl+-", self.action_insert_en_dash)
        sc("Ctrl++", self.action_zoom_in)
        sc("Ctrl+=", self.action_zoom_in)
        # ブロック操作。Windows の標準バインドは Cut=Shift+Del / Paste=Shift+Ins /
        # Copy=Ctrl+Ins なので、Ctrl を1つでも外すと切り取り・貼り付け・コピーに化ける。
        # Ctrl+Shift の組み合わせであることが QWidgetTextControl の ShortcutOverride を
        # 避ける条件でもあるため、修飾キーを減らさないこと。
        sc("Ctrl+Shift+Up", self.action_move_current_block_up)
        sc("Ctrl+Shift+Down", self.action_move_current_block_down)
        sc("Ctrl+Shift+Delete", self.action_delete_current_block).setAutoRepeat(False)
        sc("Ctrl+Shift+Insert", self.action_insert_block_below).setAutoRepeat(False)

    # ---------- fonts ----------
    def _ui_font(self) -> QFont:
        f = QFont(FONT_FAMILY.split(",")[0].strip())
        f.setPointSize(self.base_pt)
        return f

    def _content_font(self) -> QFont:
        f = QFont(FONT_FAMILY.split(",")[0].strip())
        f.setPointSize(self.base_pt + 1)
        return f

    def _title_font(self) -> QFont:
        f = QFont(FONT_FAMILY.split(",")[0].strip())
        f.setPointSize(self.base_pt + 2)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    def _apply_fonts(self) -> None:
        ui = self._ui_font()
        content = self._content_font()
        self.setFont(ui)
        self.title_edit.setFont(self._title_font())
        self.btn_add.setFont(QFont(FONT_FAMILY.split(",")[0].strip(), self.base_pt + 8))
        self.lbl_status_left.setFont(ui)
        self.lbl_status_right.setFont(ui)
        for b in self.blocks:
            b.apply_font(ui, content)

    # ---------- block management ----------
    def add_block(self, initial: bool = False, index: Optional[int] = None) -> BlockWidget:
        # initial は第1引数のまま保つこと（引数順を入れ替えると ＋ ボタンが壊れる）。
        block = BlockWidget()
        block.apply_font(self._ui_font(), self._content_font())
        # 有効域は 0 <= pos <= len(self.blocks) の閉区間。負値や超過を渡すと
        # trailing stretch の後ろに入って不変条件が壊れる。
        pos = len(self.blocks) if index is None else max(0, min(int(index), len(self.blocks)))
        self.column_layout.insertWidget(pos, block)
        self.blocks.insert(pos, block)
        block.changed.connect(self._mark_dirty)
        self._rebuild_tab_order()
        if not initial:
            self._mark_dirty()
            block.content.setFocus()
            self._reveal(block.content)
        return block

    def _destroy_block(self, block: BlockWidget) -> None:
        """ブロック1個の解体。self.blocks には触れない。"""
        self.column_layout.removeWidget(block)
        block.changed.disconnect(self._mark_dirty)
        block.setParent(None)
        block.deleteLater()

    def _clear_blocks(self) -> None:
        for b in list(self.blocks):
            self._destroy_block(b)
        self.blocks.clear()

    def _active_block(self) -> Optional[BlockWidget]:
        """フォーカス中ウィジェットを子孫に持つブロック。無ければ None。"""
        fw = QApplication.focusWidget()
        return next((b for b in self.blocks if b.isAncestorOf(fw)), None)

    def _rebuild_tab_order(self) -> None:
        """Tab フォーカス順を画面（レイアウト）順に張り直す。"""
        # btn_add / scroll を明示的に含めないと、setTabOrder の再挿入で
        # 両者がチェーン末尾へ押し出され既存の Tab 動作が退行する。
        chain: list[QWidget] = [self.title_edit, self.btn_add, self.scroll]
        for b in self.blocks:
            chain += [b.description, b.content, b.cb_show, b.ed_limit]
        for prev, nxt in zip(chain, chain[1:]):
            QWidget.setTabOrder(prev, nxt)

    def _reveal(self, widget: QWidget) -> None:
        """レイアウトを同期確定させてから widget を可視域へスクロールする。"""
        self.column_layout.activate()
        self.scroll.widget().layout().activate()
        self.scroll.ensureWidgetVisible(widget, 0, 24)

    def _block_is_empty(self, block: BlockWidget) -> bool:
        d = block.to_dict()
        return (
            not d["description"].strip()
            and not d["content"].strip()
            and d["char_limit"] == 0
            and not d["show_count"]
        )

    def _block_preview(self, block: BlockWidget) -> str:
        d = block.to_dict()
        head, _ = _split_description(d["description"])
        s = head or d["content"]
        s = " ".join(s.split())
        if not s:
            return "（未入力のブロック）"
        return s[:30] + "…" if len(s) > 30 else s

    def _confirm_delete_block(self, block: BlockWidget) -> bool:
        if self._block_is_empty(block):
            return True
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText("このブロックを削除しますか？")
        box.setInformativeText(self._block_preview(block))
        # QTranslator を入れていないため StandardButton は英語表記になる。addButton を使う。
        del_btn = box.addButton("削除", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        result = box.clickedButton() is del_btn
        box.deleteLater()
        return result

    def action_move_current_block_up(self) -> None:
        self._move_current_block(-1)

    def action_move_current_block_down(self) -> None:
        self._move_current_block(+1)

    def _move_current_block(self, delta: int) -> None:
        QApplication.inputMethod().commit()
        block = self._active_block()
        if block is None:
            return
        i = self.blocks.index(block)
        j = i + delta
        if j < 0 or j >= len(self.blocks):
            return
        saved = QApplication.focusWidget()
        self.blocks[i], self.blocks[j] = self.blocks[j], self.blocks[i]
        self.column_layout.removeWidget(block)
        self.column_layout.insertWidget(j, block)
        self._mark_dirty()
        self._rebuild_tab_order()
        if saved is not None and QApplication.focusWidget() is not saved:
            saved.setFocus(Qt.FocusReason.OtherFocusReason)
        self._reveal(saved or block.content)

    def action_delete_current_block(self) -> None:
        QApplication.inputMethod().commit()
        block = self._active_block()
        if block is None:
            return
        if len(self.blocks) == 1:
            # 「ブロックは常に1個以上」を保つため、破棄せずその場で空にリセットする。
            if self._block_is_empty(block):
                return
            if self._confirm_delete_block(block):
                block.load_from_dict({})
                self._mark_dirty()
                block.content.setFocus()
            return
        if not self._confirm_delete_block(block):
            return
        try:
            i = self.blocks.index(block)
        except ValueError:
            return
        neighbor = self.blocks[i + 1] if i + 1 < len(self.blocks) else self.blocks[i - 1]
        # 破棄より先にフォーカスを移す（後だと勝手に別ブロックへ飛んでビューが跳ねる）。
        neighbor.content.setFocus()
        self.blocks.pop(i)
        self._destroy_block(block)
        self._rebuild_tab_order()
        self._mark_dirty()
        self._reveal(neighbor.content)

    def action_insert_block_below(self) -> None:
        QApplication.inputMethod().commit()
        block = self._active_block()
        if block is not None:
            self.add_block(index=self.blocks.index(block) + 1)
        else:
            self.add_block()

    # ---------- dirty / status ----------
    def _snapshot(self) -> str:
        return json.dumps(self._serialize(), ensure_ascii=False, sort_keys=True)

    def _mark_dirty(self, *_args) -> None:
        if self._loading:
            return
        new_dirty = self._snapshot() != self._saved_snapshot
        if new_dirty != self.dirty:
            self.dirty = new_dirty
            self._update_status()
            self._update_window_title()

    def _update_status(self) -> None:
        self.lbl_status_left.setText(
            "未保存の変更あり" if self.dirty else "保存済み"
        )
        self.lbl_status_right.setText(
            str(self.current_path) if self.current_path else "新規"
        )

    def _update_window_title(self) -> None:
        name = self.current_path.name if self.current_path else "新規"
        mark = "*" if self.dirty else ""
        self.setWindowTitle(f"{mark}{name} — {APP_NAME}")

    # ---------- serialize ----------
    def _serialize(self) -> dict:
        return {
            "version": 1,
            "title": self.title_edit.text(),
            "blocks": [b.to_dict() for b in self.blocks],
        }

    def _load_data(self, data: dict) -> None:
        self._loading = True
        try:
            self._clear_blocks()
            self.title_edit.setText(data.get("title", ""))
            blocks_data = data.get("blocks", [])
            if not blocks_data:
                blocks_data = [
                    {"description": "", "content": "", "char_limit": 0, "show_count": False}
                ]
            for bd in blocks_data:
                block = BlockWidget()
                block.apply_font(self._ui_font(), self._content_font())
                block.load_from_dict(bd)
                self.column_layout.insertWidget(self.column_layout.count() - 1, block)
                self.blocks.append(block)
                block.changed.connect(self._mark_dirty)
        finally:
            self._loading = False
        # _clear_blocks で全ブロックを破棄しているのでチェーンを張り直す。
        self._rebuild_tab_order()
        self._saved_snapshot = self._snapshot()
        self.dirty = False
        self._update_status()
        self._update_window_title()

    # ---------- actions ----------
    def _confirm_discard(self) -> Optional[bool]:
        """Return: True = save first / False = discard / None = cancel."""
        if not self.dirty:
            return False
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("変更が保存されていません。どうしますか？")
        save_btn = box.addButton("保存する", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("保存しない", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            return True
        if clicked is discard_btn:
            return False
        return None

    def action_new(self) -> None:
        decision = self._confirm_discard()
        if decision is None:
            return
        if decision is True:
            if not self.action_save():
                return
        self._load_data({"version": 1, "title": "", "blocks": []})
        self.current_path = None
        self.dirty = False
        self._update_status()
        self._update_window_title()
        if self.blocks:
            self.blocks[0].content.setFocus()

    def action_open(self) -> None:
        decision = self._confirm_discard()
        if decision is None:
            return
        if decision is True:
            if not self.action_save():
                return
        path_str, _ = QFileDialog.getOpenFileName(
            self, "ファイルを開く", "", FILE_FILTER_NATIVE
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            data = _validate_data(raw)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            QMessageBox.warning(self, APP_NAME, f"ファイルを開けませんでした:\n{e}")
            return
        self._load_data(data)
        self.current_path = path
        self.dirty = False
        self._update_status()
        self._update_window_title()
        if self.blocks:
            self.blocks[0].content.setFocus()

    def action_save(self) -> bool:
        if self.current_path is None:
            return self.action_save_as()
        return self._write_to(self.current_path)

    def action_save_as(self) -> bool:
        suggested = _sanitize_filename(self.title_edit.text()) + FILE_EXT
        path_str, _ = QFileDialog.getSaveFileName(
            self, "名前をつけて保存", suggested, FILE_FILTER_NATIVE
        )
        if not path_str:
            return False
        path = Path(path_str)
        if path.suffix.lower() != FILE_EXT:
            path = path.with_suffix(FILE_EXT)
        if self._write_to(path):
            self.current_path = path
            self._update_status()
            self._update_window_title()
            return True
        return False

    def _write_to(self, path: Path) -> bool:
        data = self._serialize()
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"保存に失敗しました:\n{e}")
            return False
        self._saved_snapshot = self._snapshot()
        self.dirty = False
        self._update_status()
        self._update_window_title()
        return True

    def action_export(self) -> None:
        suggested = _sanitize_filename(self.title_edit.text())
        path_str, selected_filter = QFileDialog.getSaveFileName(
            self, "エクスポート", suggested, EXPORT_FILTER
        )
        if not path_str:
            return
        path = Path(path_str)
        is_md = "Markdown" in (selected_filter or "")
        ext = ".md" if is_md else ".txt"
        if path.suffix.lower() not in (".md", ".txt"):
            path = path.with_suffix(ext)
        else:
            is_md = path.suffix.lower() == ".md"
        data = self._serialize()
        text = _export_markdown(data) if is_md else _export_text(data)
        try:
            with path.open("w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"エクスポートに失敗しました:\n{e}")

    def action_zoom_in(self) -> None:
        self._set_zoom(self.base_pt + 1)

    def action_zoom_out(self) -> None:
        self._set_zoom(self.base_pt - 1)

    def action_zoom_reset(self) -> None:
        self._set_zoom(FONT_DEFAULT_PT)

    def _set_zoom(self, pt: int) -> None:
        pt = max(FONT_MIN_PT, min(FONT_MAX_PT, pt))
        if pt == self.base_pt:
            return
        self.base_pt = pt
        self._apply_fonts()

    def action_insert_en_dash(self) -> None:
        w = QApplication.focusWidget()
        if isinstance(w, (QPlainTextEdit, QTextEdit)):
            cursor = w.textCursor()
            cursor.insertText(EN_DASH)
        elif isinstance(w, QLineEdit):
            w.insert(EN_DASH)

    # ---------- events ----------
    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802
        if ev.type() == QEvent.Type.Wheel and (
            ev.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            delta = ev.angleDelta().y()
            if delta > 0:
                self.action_zoom_in()
            elif delta < 0:
                self.action_zoom_out()
            return True
        if ev.type() == QEvent.Type.Resize and obj is self.scroll.viewport():
            w = int(self.scroll.viewport().width() * COLUMN_WIDTH_RATIO)
            self.column.setFixedWidth(max(200, w))
        return super().eventFilter(obj, ev)

    def closeEvent(self, e) -> None:  # noqa: N802
        decision = self._confirm_discard()
        if decision is None:
            e.ignore()
            return
        if decision is True:
            if not self.action_save():
                e.ignore()
                return
        e.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(QSS)
    base = QFont(FONT_FAMILY.split(",")[0].strip(), FONT_DEFAULT_PT)
    app.setFont(base)
    win = EditorWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
