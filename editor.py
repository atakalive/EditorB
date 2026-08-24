"""EditorB — research proposal block editor."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QMimeData, QObject, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QIntValidator,
    QKeySequence,
    QPalette,
    QShortcut,
    QTextBlock,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
    QTextFormat,
    QTextList,
    QTextListFormat,
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
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
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

FILE_VERSION = 2
INDENT_MAX = 6
# 1段のインデントを Word へ渡すときの pt 値（_word_ready_html）。
WORD_INDENT_PT = 24
DIRTY_DEBOUNCE_MS = 300
BAR_DELAY_MS = 120

# 文字数カウントから除外する文字。toPlainText() は U+2028 / U+2029 を "\n" に
# 正規化するので、ここで指定するのは改行と OBJECT REPLACEMENT CHARACTER だけでよい。
_COUNT_STRIP = {ord("\n"): None, ord("\r"): None, 0xFFFC: None}

# サニタイズで落とすブロック書式プロパティ。
# ObjectIndex（リスト所属）は消してはいけない。BlockIndent は明示設定する。
_BLOCK_KILL = (
    QTextFormat.Property.BlockTopMargin,
    QTextFormat.Property.BlockBottomMargin,
    QTextFormat.Property.BlockLeftMargin,
    QTextFormat.Property.BlockRightMargin,
    QTextFormat.Property.TextIndent,
    QTextFormat.Property.LineHeight,
    QTextFormat.Property.LineHeightType,
    QTextFormat.Property.BlockNonBreakableLines,
    QTextFormat.Property.BlockQuoteLevel,
    QTextFormat.Property.HeadingLevel,
    QTextFormat.Property.BlockAlignment,
    QTextFormat.Property.BackgroundBrush,
    QTextFormat.Property.TabPositions,
    QTextFormat.Property.PageBreakPolicy,
)

_RE_STYLE_ATTR = re.compile(r'style="([^"]*)"')
_RE_BLOCK_INDENT = re.compile(r"-qt-block-indent:\s*(\d+)")

_SUPER = QTextCharFormat.VerticalAlignment.AlignSuperScript
_SUB = QTextCharFormat.VerticalAlignment.AlignSubScript
_NBSP = "\u00a0"
_SOFT_BREAK = "\u2028"


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
QTextEdit#content {
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

QFrame#formatbar {
    background: #333333;
    border: 1px solid #4a4a4a;
    border-radius: 5px;
}
QFrame#formatbar QToolButton {
    background: transparent;
    color: #d4d4d4;
    border: none;
    border-radius: 3px;
    padding: 2px 5px;
    min-width: 20px;
}
QFrame#formatbar QToolButton:hover { background: #45494d; }
QFrame#formatbar QToolButton:checked { background: #0e639c; color: #ffffff; }
QFrame#formatbar QToolButton#fb_bold { font-weight: bold; }
QFrame#formatbar QToolButton#fb_italic { font-style: italic; }
QFrame#formatbar QToolButton#fb_underline { text-decoration: underline; }
QFrame#formatbar QToolButton#fb_strike { text-decoration: line-through; }
QFrame#formatbar QLabel#fb_sep {
    color: #555;
    background: transparent;
}

QMenu {
    background: #252526;
    color: #d4d4d4;
    border: 1px solid #444;
    padding: 4px;
}
QMenu::item {
    padding: 4px 24px 4px 20px;
    border-radius: 3px;
}
QMenu::item:selected { background: #0e639c; color: #ffffff; }
QMenu::item:disabled { color: #5a5a5a; }
QMenu::separator {
    height: 1px;
    background: #3a3a3a;
    margin: 4px 6px;
}
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


# ---------------------------------------------------------------------------
# リッチテキスト用ヘルパ（サニタイズ / HTML 整形 / 選択範囲）
# ---------------------------------------------------------------------------


def _clean_char_format(src: QTextCharFormat) -> QTextCharFormat:
    """ホワイトリスト方式で文字書式を作り直す。

    ここに列挙しないものは構造上すべて落ちる（フォント名 / サイズ / 文字色 /
    背景色 / ハイパーリンク / 字送り / 大文字化 …）。
    """
    out = QTextCharFormat()
    if src.fontWeight() >= QFont.Weight.DemiBold:
        out.setFontWeight(QFont.Weight.Bold)
    if src.fontItalic():
        out.setFontItalic(True)
    if src.fontUnderline():
        out.setFontUnderline(True)
    if src.fontStrikeOut():
        out.setFontStrikeOut(True)
    va = src.verticalAlignment()
    if va in (_SUPER, _SUB):
        out.setVerticalAlignment(va)
    return out


def _fragments(block: QTextBlock) -> list:
    """(position, length, charFormat) のスナップショット。

    setCharFormat はフラグメントを結合・分割するので、イテレート中に書き換えると
    壊れる。必ず先に読み切ってから書く。
    """
    out = []
    for it in block:
        frag = it.fragment()
        if frag.isValid() and frag.length() > 0:
            out.append((frag.position(), frag.length(), frag.charFormat()))
    return out


def _normalize_lists(doc: QTextDocument) -> None:
    """各リストオブジェクトのメンバー間に「自段数以下の非メンバー」が挟まらないよう分割正規化する。

    同じ元リストが複数の gap をまたいで壊れていても gap ごとに新リストへ切り出す
    （単一パスで全 gap を修復）。リスト同一性は Python の id() ではなく安定した
    blockFormat().objectIndex() で判定する（PySide は textList() を呼ぶ度に別ラッパを
    返すため id() は信頼できない）。
    """
    # 段数 -> (現在開いている objectIndex, その run の差し替え先 or None=元のまま)
    active: dict[int, tuple[int, Optional[QTextList]]] = {}
    opened: set[int] = set()  # これまで開いた objectIndex
    b = doc.begin()
    while b.isValid():
        tl = b.textList()
        if tl is not None:
            d = tl.format().indent()
            oi = b.blockFormat().objectIndex()
            for k in [k for k in active if k > d]:      # 自分より深い段は閉じる
                del active[k]
            cur = active.get(d)
            if cur is not None and cur[0] == oi:        # 同じ run が連続 -> 継続
                if cur[1] is not None:
                    cur[1].add(b)                       # 分割 run なら差し替え先へ足す
            elif oi in opened:                          # 一度閉じた後の再登場 = 新しい gap
                active[d] = (oi, QTextCursor(b).createList(tl.format()))
            else:                                       # 初 run -> 元リストのまま
                active[d] = (oi, None)
                opened.add(oi)
        else:
            d = b.blockFormat().indent()
            for k in [k for k in active if k >= d]:     # 非リスト行は自段数以上を閉じる
                del active[k]
        b = b.next()


def sanitize_document(doc: QTextDocument, map_margins: bool = True) -> None:
    """貼り付け・ドロップ・ファイル読み込みの3経路すべてを通す正規化。

    許可した書式（太字/斜体/下線/取り消し線/上下付き/リスト/インデント）だけを残し、
    フォント・色・余白といった外来の指定を落とす。読み込み時にも通すことで、
    setHtml がすべての char format に焼き付ける FontFamilies / FontPointSize
    （＝ズームが効かなくなる原因）と、<p> に注入される 12px の段落余白を潰す。
    """
    # 1. 画像・OLE 等のインラインオブジェクトを削除。位置ズレを避けるため後ろから。
    kill = []
    b = doc.begin()
    while b.isValid():
        for it in b:
            frag = it.fragment()
            if not frag.isValid() or frag.length() <= 0:
                continue
            cf = frag.charFormat()
            if cf.isImageFormat() or cf.objectType() != QTextFormat.ObjectTypes.NoObject:
                kill.append((frag.position(), frag.length()))
        b = b.next()
    for pos, length in sorted(kill, reverse=True):
        c = QTextCursor(doc)
        c.setPosition(pos)
        c.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()

    indent_width = doc.indentWidth() or 1.0
    b = doc.begin()
    while b.isValid():
        # 2. 文字書式をホワイトリストで作り直す。
        for pos, length, cf in _fragments(b):
            c = QTextCursor(doc)
            c.setPosition(pos)
            c.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            c.setCharFormat(_clean_char_format(cf))

        # 3. ブロック書式。⚠️ 順序が load-bearing:
        #    margin を消す「前に」段数変換を済ませること（消してから読むと変換元が失われる）。
        bf0 = b.blockFormat()
        if map_margins and bf0.indent() == 0 and bf0.leftMargin() > 0:
            target_indent = int(round(bf0.leftMargin() / indent_width))
        else:
            target_indent = bf0.indent()
        target_indent = max(0, min(INDENT_MAX, target_indent))
        # 新規 QTextBlockFormat() を作ると ObjectIndex（リスト所属）が消えて
        # <ul><li> が <p> に落ちる。必ずコピーして不要プロパティだけ消す。
        bf = QTextBlockFormat(bf0)
        for prop in _BLOCK_KILL:
            bf.clearProperty(prop)
        bf.setIndent(target_indent)
        QTextCursor(b).setBlockFormat(bf)

        # 4. ブロック文字書式のリセット。これを忘れると Qt が style= 属性を2つ持つ
        #    不正な <li> を出力する（Word / ブラウザは最初の属性しか見ない）。
        QTextCursor(b).setBlockCharFormat(QTextCharFormat())

        # 5. NBSP を通常スペースへ（Word の HTML はインデント代わりに NBSP を並べる）。
        text = b.text()
        if _NBSP in text:
            start = b.position()
            for i, ch in enumerate(text):
                if ch == _NBSP:
                    c = QTextCursor(doc)
                    c.setPosition(start + i)
                    c.setPosition(start + i + 1, QTextCursor.MoveMode.KeepAnchor)
                    c.insertText(" ")
        b = b.next()

    # 6. 壊れたリスト構造（<p> がリスト直下に挟まる不正 HTML）を取り込み時に修復。
    _normalize_lists(doc)


def doc_has_formatting(doc: QTextDocument) -> bool:
    """表示上の書式（リスト / インデント / 文字修飾）があるか。文字列を組まないので速い。"""
    b = doc.begin()
    while b.isValid():
        if b.textList() is not None or b.blockFormat().indent():
            return True
        for it in b:
            frag = it.fragment()
            if not frag.isValid():
                continue
            cf = frag.charFormat()
            if (
                cf.fontWeight() >= QFont.Weight.DemiBold
                or cf.fontItalic()
                or cf.fontUnderline()
                or cf.fontStrikeOut()
                or cf.verticalAlignment() in (_SUPER, _SUB)
            ):
                return True
        b = b.next()
    return False


def _needs_html(doc: QTextDocument) -> bool:
    """保存に HTML が必要か。保存要否の判定は必ずこちらを使う。

    toPlainText() は U+2028 / U+2029 を "\\n" に潰すため、無修飾でソフト改行だけを
    含むブロックを doc_has_formatting だけで判定すると v1（plain）保存になり、
    再読込で setPlainText がソフト改行を段落区切りに化けさせる。
    """
    return doc_has_formatting(doc) or _SOFT_BREAK in doc.toRawText()


def _word_ready_html(html: str) -> str:
    """Qt のフラグメント HTML を、Word でも同じ見た目になるようにする。

    -qt-block-indent:N (N>0) を持つ style 属性の**末尾**に margin-left:N*24pt を追記する。

    ⚠️ 置換ではなく追記であることが本質。Qt の CSS 長さパーサは px / em / ex /
    単位なし しか解釈せず pt は 0 になるので、Word は pt を読み、Qt は pt を無視して
    -qt-block-indent を読む＝どちらも二重にならない。置換すると EditorB 内での
    コピー＆ペーストやドラッグ移動でインデントが完全に消える。
    ⚠️ 既知の脆さ: この手口は「Qt が pt を解釈しない」ことに全面依存している。
    将来 Qt が CSS の pt を解釈し始めると、内部コピペ／ドラッグ移動で字下げが倍になる。
    追記先を style 属性の末尾にするのは、Qt が同じ style 内に margin-left:0px を
    先に出力するため（CSS の後勝ちで我々の Npt を確実に勝たせる）。
    """
    def repl(m: re.Match) -> str:
        style = m.group(1)
        bi = _RE_BLOCK_INDENT.search(style)
        if bi is None or not int(bi.group(1)):
            return m.group(0)                                   # 段数 0 / 非該当は素通し
        pt = int(bi.group(1)) * WORD_INDENT_PT
        return f'style="{style.rstrip()} margin-left:{pt}pt;"'  # style 末尾＝最後の宣言
    return _RE_STYLE_ATTR.sub(repl, html)


def _strip_fragment_markers(html: str) -> str:
    """QTextDocumentFragment.toHtml() が先頭/末尾の <li>/<p> の内側に埋め込む
    <!--StartFragment--> / <!--EndFragment--> を除去する。

    ⚠️ これを残したまま QTextDocument.setHtml() へ通すと、コメントが <li>/<p> の
    内側にあるせいで Qt 6.11.0 が当該ブロックの list 所属（ObjectIndex）と
    -qt-block-indent を落とす（＝保存→再読込・内部コピペでリストと段落インデントが
    黙って全消失する）。setHtml へ渡す前と保存 HTML の生成時に必ず剥がす。
    Word へのコピー経路（out.setHtml で載せるだけ・再パースしない）では剥がさない
    ——Qt がこのコメントから CF_HTML のフラグメントオフセットを計算するため。
    """
    return html.replace("<!--StartFragment-->", "").replace("<!--EndFragment-->", "")


def _selected_blocks(cur: QTextCursor) -> list:
    """選択にかかっているブロックの一覧。"""
    doc = cur.document()
    lo, hi = min(cur.anchor(), cur.position()), max(cur.anchor(), cur.position())
    first, last = doc.findBlock(lo), doc.findBlock(hi)
    # 選択終端がブロック先頭ちょうどのとき、そのブロックは選択に含まれていない。
    # （1〜2行目をドラッグして3行目の先頭で離す、という最も普通の操作がこれ）
    if hi > lo and hi == last.position():
        last = last.previous()
    if not last.isValid() or last.blockNumber() < first.blockNumber():
        last = first
    out, b = [], first
    while b.isValid():
        out.append(b)
        if b.blockNumber() == last.blockNumber():
            break
        b = b.next()
    return out


def _list_format(style: QTextListFormat.Style, indent: int) -> QTextListFormat:
    lf = QTextListFormat()
    lf.setStyle(style)
    lf.setIndent(max(1, indent))
    return lf


class RichTextEdit(QTextEdit):
    """本文用のリッチテキスト欄。自動伸長し、Word と往復できる範囲の書式だけを扱う。"""

    escape_pressed = Signal()

    # (メソッド名, ラベル, ツールチップ, ボタンの objectName or None)
    COMMANDS = (
        ("toggle_bold", "B", "太字 (Ctrl+B)", "fb_bold"),
        ("toggle_italic", "I", "斜体 (Ctrl+I)", "fb_italic"),
        ("toggle_underline", "U", "下線 (Ctrl+U)", "fb_underline"),
        ("toggle_strike", "S", "取り消し線 (Ctrl+Shift+X)", "fb_strike"),
        (None, "│", None, None),
        ("toggle_superscript", "x²", "上付き (Ctrl+.)", None),
        ("toggle_subscript", "x₂", "下付き (Ctrl+,)", None),
        (None, "│", None, None),
        ("toggle_bullet_list", "•—", "箇条書き (Ctrl+Shift+L)", None),
        ("toggle_numbered_list", "1.", "番号付きリスト (Ctrl+Shift+N)", None),
        (None, "│", None, None),
        ("indent_more", "→|", "インデント + (Ctrl+M / Tab)", None),
        ("indent_less", "|←", "インデント − (Ctrl+Shift+M / Shift+Tab)", None),
        (None, "│", None, None),
        ("clear_format", "Tx", "書式クリア (Ctrl+Space)", None),
    )
    # チェック状態を持つコマンド
    CHECKABLE = (
        "toggle_bold",
        "toggle_italic",
        "toggle_underline",
        "toggle_strike",
        "toggle_superscript",
        "toggle_subscript",
        "toggle_bullet_list",
        "toggle_numbered_list",
    )

    def __init__(
        self,
        min_lines: int,
        placeholder: str,
        object_name: str,
        placeholder_color: str = "#444",
    ) -> None:
        super().__init__()
        self._min_lines = min_lines
        self._adjusting = False
        self.setObjectName(object_name)
        self.setPlaceholderText(placeholder)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(placeholder_color))
        self.setPalette(pal)
        self.setAcceptRichText(True)
        # 「*」で勝手に箇条書きにされるのを殺す。
        self.setAutoFormatting(QTextEdit.AutoFormattingFlag.AutoNone)
        self.setTabChangesFocus(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        self._build_shortcuts()
        # setHtml は同じ QTextDocument を再利用し documentLayout も不変なので、
        # ここで1回つなげば読み込み後も張り直し不要。
        self.document().documentLayout().documentSizeChanged.connect(
            lambda *_: self._adjust_height()
        )
        self._adjust_height()

    # ---------- shortcuts ----------
    def _build_shortcuts(self) -> None:
        # WidgetShortcut にすることで、フォーカス中のエディタだけが反応する
        # （ウィンドウレベルだとタイトル欄の編集中に Ctrl+B が誤発火する）。
        def sc(seq: str, fn) -> None:
            s = QShortcut(QKeySequence(seq), self, activated=fn)
            s.setContext(Qt.ShortcutContext.WidgetShortcut)

        sc("Ctrl+B", self.toggle_bold)
        sc("Ctrl+I", self.toggle_italic)
        sc("Ctrl+U", self.toggle_underline)
        sc("Ctrl+Shift+X", self.toggle_strike)
        # Word の Ctrl+= / Ctrl+Shift+= は Ctrl+= のズームイン、JIS の Ctrl+-（en dash）と
        # 物理的に衝突するので採用しない。Google Docs 準拠の Ctrl+. / Ctrl+, を使う。
        sc("Ctrl+.", self.toggle_superscript)
        sc("Ctrl+,", self.toggle_subscript)
        sc("Ctrl+Space", self.clear_format)
        sc("Ctrl+\\", self.clear_format)   # IME が Ctrl+Space を取る環境向けの保険
        sc("Ctrl+Shift+L", self.toggle_bullet_list)
        sc("Ctrl+Shift+N", self.toggle_numbered_list)
        sc("Ctrl+M", self.indent_more)
        sc("Ctrl+Shift+M", self.indent_less)
        sc("Ctrl+Shift+V", self.paste_plain)

    # ---------- geometry ----------
    def setFont(self, font: QFont) -> None:  # noqa: N802
        super().setFont(font)
        self.viewport().setFont(font)
        doc = self.document()
        doc.setDefaultFont(font)
        # 字下げ幅もズームに追従させる。Qt は行頭記号を字下げ幅の内側に右寄せで描くため、
        # 幅が足りないと番号の先頭桁が切れる（3桁「100.」や等幅フォントで破綻する）。
        doc.setIndentWidth(max(24.0, QFontMetricsF(font).height() * 2.2))
        self.viewport().update()
        self._adjust_height()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._adjust_height()

    def _adjust_height(self) -> None:
        if self._adjusting:                                   # 再入ガード
            return
        self._adjusting = True
        try:
            doc = self.document()
            doc_h = doc.size().height()                       # 2*documentMargin を含む
            fm = QFontMetrics(self.font())
            min_h = fm.lineSpacing() * self._min_lines + 2 * doc.documentMargin()
            m = self.contentsMargins()
            total = (int(math.ceil(max(doc_h, min_h)))
                     + m.top() + m.bottom() + 2 * self.frameWidth() + 2)
            if self.height() != total:
                self.setFixedHeight(total)
        finally:
            self._adjusting = False

    # ---------- 文字書式 ----------
    def _probe_format(self) -> QTextCharFormat:
        """状態判定用の文字書式。選択があればその先頭の文字書式（Word と同じ）。"""
        cur = self.textCursor()
        if cur.hasSelection():
            doc = self.document()
            pos = min(cur.anchor(), cur.position()) + 1
            c = QTextCursor(doc)
            c.setPosition(min(pos, doc.characterCount() - 1))
            return c.charFormat()
        return self.currentCharFormat()

    def _merge_char(self, fmt: QTextCharFormat) -> None:
        cur = self.textCursor()
        cur.beginEditBlock()
        # 選択が無いとき WordUnderCursor へフォールバックしない
        # （日本語に語境界は無く、文節ごと不意に太字になる）。
        cur.mergeCharFormat(fmt)
        cur.endEditBlock()
        self.mergeCurrentCharFormat(fmt)

    def toggle_bold(self) -> None:
        f = QTextCharFormat()
        on = self._probe_format().fontWeight() >= QFont.Weight.DemiBold
        f.setFontWeight(QFont.Weight.Normal if on else QFont.Weight.Bold)
        self._merge_char(f)

    def toggle_italic(self) -> None:
        f = QTextCharFormat()
        f.setFontItalic(not self._probe_format().fontItalic())
        self._merge_char(f)

    def toggle_underline(self) -> None:
        f = QTextCharFormat()
        f.setFontUnderline(not self._probe_format().fontUnderline())
        self._merge_char(f)

    def toggle_strike(self) -> None:
        f = QTextCharFormat()
        f.setFontStrikeOut(not self._probe_format().fontStrikeOut())
        self._merge_char(f)

    def _toggle_vertical(self, va) -> None:
        f = QTextCharFormat()
        current = self._probe_format().verticalAlignment()
        normal = QTextCharFormat.VerticalAlignment.AlignNormal
        f.setVerticalAlignment(normal if current == va else va)
        self._merge_char(f)

    def toggle_superscript(self) -> None:
        self._toggle_vertical(_SUPER)

    def toggle_subscript(self) -> None:
        self._toggle_vertical(_SUB)

    def clear_format(self) -> None:
        """文字書式のみリセット（Word の Ctrl+Space と同じ。リストは外さない）。"""
        cur = self.textCursor()
        blank = QTextCharFormat()
        if cur.hasSelection():
            cur.beginEditBlock()
            cur.setCharFormat(blank)
            cur.endEditBlock()
        self.setCurrentCharFormat(blank)

    # ---------- リスト / インデント ----------
    def _span_cursor(self, blocks: list) -> QTextCursor:
        c = QTextCursor(self.document())
        c.setPosition(blocks[0].position())
        last = blocks[-1]
        c.setPosition(last.position() + last.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        return c

    def _unset_list(self, blocks: list) -> None:
        for b in blocks:
            tl = b.textList()
            if tl is not None:
                # setObjectIndex(-1) はプロパティを消すのでマージが no-op になり効かない。
                tl.remove(b)
            bf = QTextBlockFormat(b.blockFormat())
            bf.setIndent(0)      # remove() はブロックの indent を 0 -> 1 に上げる
            QTextCursor(b).setBlockFormat(bf)

    def _toggle_list(self, style: QTextListFormat.Style) -> None:
        doc = self.document()
        cur = self.textCursor()
        blocks = _selected_blocks(cur)
        tl = blocks[0].textList()
        already = tl is not None and tl.format().style() == style
        cur.beginEditBlock()
        try:
            if already:
                self._unset_list(blocks)
            else:
                indent = tl.format().indent() if tl is not None else 1
                self._span_cursor(blocks).createList(_list_format(style, indent))
            _normalize_lists(doc)
        finally:
            cur.endEditBlock()

    def toggle_bullet_list(self) -> None:
        self._toggle_list(QTextListFormat.Style.ListDisc)

    def toggle_numbered_list(self) -> None:
        self._toggle_list(QTextListFormat.Style.ListDecimal)

    def _change_indent(self, delta: int) -> None:
        doc = self.document()
        cur = self.textCursor()
        blocks = _selected_blocks(cur)
        tl = blocks[0].textList()
        cur.beginEditBlock()
        try:
            if tl is not None:
                # QTextListFormat.setIndent を共有リストへ掛けてはいけない
                # （途中1項目だけ選んでも未選択項目まで全部ネストする）。
                # 正しくは「選択ブロックを別リストに切り出す」。
                k = tl.format().indent()
                new = k + delta
                if new < 1:
                    self._unset_list(blocks)
                else:
                    new = min(new, INDENT_MAX)
                    if new != k:
                        lf = QTextListFormat(tl.format())
                        lf.setIndent(new)
                        self._span_cursor(blocks).createList(lf)
            else:
                for b in blocks:
                    bf = QTextBlockFormat(b.blockFormat())
                    bf.setIndent(max(0, min(INDENT_MAX, bf.indent() + delta)))
                    QTextCursor(b).setBlockFormat(bf)
            _normalize_lists(doc)
        finally:
            cur.endEditBlock()

    def indent_more(self) -> None:
        self._change_indent(+1)

    def indent_less(self) -> None:
        self._change_indent(-1)

    # ---------- コピー / 貼り付け ----------
    def createMimeDataFromSelection(self) -> QMimeData:  # noqa: N802
        src = super().createMimeDataFromSelection()
        out = QMimeData()
        if src.hasHtml():
            # 選択フラグメントを scratch に取り込んで sanitize する。狙いは内部編集で
            # 付いた block char format 由来の「style= を2つ持つ <li>」を潰すこと
            # （Word / ブラウザは最初の style しか見ないので余白・インデントが落ちる）。
            # 取り込み時は StartFragment を剥がさないとリスト所属が落ちるので剥がす。
            scratch = QTextDocument()
            scratch.setDefaultFont(self.document().defaultFont())
            scratch.setIndentWidth(self.document().indentWidth())
            scratch.setHtml(_strip_fragment_markers(src.html()))
            sanitize_document(scratch, map_margins=False)
            # 再直列化で StartFragment が付き直る。out.setHtml で載せ直すので Qt が
            # CF_HTML のバイトオフセットを再計算する（この経路ではマーカーを残す）。
            html = _word_ready_html(QTextDocumentFragment(scratch).toHtml())
            out.setHtml(html)
        # text/plain は必須（メモ帳・Paste Special・ターミナル用）。
        out.setText(src.text())
        return out

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        # 判定は「画像/URL が有るか」ではなく「使える html/text が無いか」で行う。
        # Windows の Word はリッチコピー時に CF_HTML と並行して選択範囲のビットマップも
        # 載せるため、普通の Word コピーでも hasImage() は True になる。
        if source.hasHtml():
            return True
        if source.hasUrls() and any(u.isLocalFile() for u in source.urls()):
            return False                       # Explorer のファイルドロップを拒否
        if source.hasText():
            return True                        # プレーンテキスト／file 以外の URL は受理
        return False                           # html も text も無い（純画像等）は拒否

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        cur = self.textCursor()
        if source.hasHtml():
            scratch = QTextDocument()
            scratch.setDefaultFont(self.document().defaultFont())
            # 余白 -> 段数変換の基準を揃える
            scratch.setIndentWidth(self.document().indentWidth())
            # StartFragment コメントを剥がしてから setHtml（内部コピペで我々自身が
            # 載せたフラグメント HTML はこれを含み、残すとリスト所属が落ちる）。
            scratch.setHtml(_strip_fragment_markers(source.html()))
            sanitize_document(scratch)
            cur.beginEditBlock()
            cur.insertFragment(QTextDocumentFragment(scratch))
            cur.endEditBlock()
        elif source.hasText():
            # \r\n / \r / U+2029 / U+2028 は Qt が正規化する
            cur.insertText(source.text())

    def paste_plain(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.textCursor().insertText(text)

    # ---------- コンテキストメニュー ----------
    def contextMenuEvent(self, e) -> None:  # noqa: N802
        menu = self.createStandardContextMenu(e.pos())
        menu.addSeparator()
        menu.addAction("書式なしで貼り付け\tCtrl+Shift+V", self.paste_plain)
        sub: QMenu = menu.addMenu("書式")
        for name, label, tip, _obj in self.COMMANDS:
            if name is None:
                sub.addSeparator()
                continue
            sub.addAction(tip or label, getattr(self, name))
        menu.exec(e.globalPos())
        menu.deleteLater()

    # ---------- キー入力 ----------
    def keyPressEvent(self, e) -> None:  # noqa: N802
        # Tab / Shift+Tab はショートカットより先に Qt がフォーカス移動として解決するので
        # ここで処理する（Shift+Tab は Key_Backtab として届く）。
        if e.key() == Qt.Key.Key_Tab and e.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.indent_more()
            e.accept()
            return
        if e.key() == Qt.Key.Key_Backtab:
            self.indent_less()
            e.accept()
            return
        if e.key() == Qt.Key.Key_Escape:
            # バーを隠すが accept せず伝播させる。
            self.escape_pressed.emit()
        super().keyPressEvent(e)


class FormatBar(QFrame):
    """テキスト選択時に浮かぶ書式ツールバー。

    トップレベルウィンドウではなく central widget の子にする（トップレベルだと
    クリック時に一部の Windows 環境でメインウィンドウが非アクティブ化し、
    選択範囲が非アクティブ配色になって壊れて見える）。
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("formatbar")
        self.setFrameShape(QFrame.Shape.NoFrame)
        # フォーカスを奪うと選択が消えて全機能が死ぬ。NoFocus のウィジェットは
        # クリックフォーカスを受け取らないので構造的に奪えなくなる。
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._editor: Optional[RichTextEdit] = None
        self._syncing = False
        self._buttons: dict = {}

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(1)
        for name, label, tip, obj in RichTextEdit.COMMANDS:
            if name is None:
                sep = QLabel(label)
                sep.setObjectName("fb_sep")
                sep.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                lay.addWidget(sep)
                continue
            btn = QToolButton(self)
            btn.setText(label)
            btn.setToolTip(tip)
            if obj:
                btn.setObjectName(obj)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if name in RichTextEdit.CHECKABLE:
                btn.setCheckable(True)
            # toggled ではなく clicked（sync_state の setChecked が再発火しないように）。
            btn.clicked.connect(lambda _checked=False, n=name: self._run(n))
            lay.addWidget(btn)
            self._buttons[name] = btn

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(BAR_DELAY_MS)
        self._timer.timeout.connect(self._maybe_show)
        self.hide()

    # ---------- attach / detach ----------
    def attach(self, editor: RichTextEdit) -> None:
        if editor is self._editor:
            return
        self.detach()
        editor.selectionChanged.connect(self._on_selection_changed)
        editor.cursorPositionChanged.connect(self.sync_state)
        editor.currentCharFormatChanged.connect(self._on_format_changed)
        editor.escape_pressed.connect(self.hide)
        self._editor = editor

    def detach(self) -> None:
        ed = self._editor
        self._editor = None
        self._timer.stop()
        if ed is not None:
            ed.selectionChanged.disconnect(self._on_selection_changed)
            ed.cursorPositionChanged.disconnect(self.sync_state)
            ed.currentCharFormatChanged.disconnect(self._on_format_changed)
            ed.escape_pressed.disconnect(self.hide)
        self.hide()

    def detach_if(self, editor) -> None:
        if self._editor is editor:
            self.detach()

    # ---------- triggers ----------
    def _on_selection_changed(self) -> None:
        ed = self._editor
        if ed is None or not ed.textCursor().hasSelection():
            self.hide()
            return
        self._timer.start()

    def _on_format_changed(self, _fmt=None) -> None:
        self.sync_state()

    def _maybe_show(self) -> None:
        ed = self._editor
        if ed is None or not ed.textCursor().hasSelection():
            return
        # ドラッグ選択中のちらつきを防ぐ。
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            self._timer.start()
            return
        self.sync_state()
        self.adjustSize()
        self.show()
        self.raise_()
        self.reposition()

    def reposition(self) -> None:
        ed = self._editor
        parent = self.parentWidget()
        if ed is None or parent is None or not self.isVisible():
            return
        cur = ed.textCursor()
        if not cur.hasSelection():
            self.hide()
            return
        c = QTextCursor(ed.document())
        c.setPosition(min(cur.anchor(), cur.position()))
        rect = ed.cursorRect(c)
        vp = ed.viewport()
        if not vp.rect().intersects(rect):
            self.hide()
            return
        top = parent.mapFromGlobal(vp.mapToGlobal(rect.topLeft()))
        bottom = parent.mapFromGlobal(vp.mapToGlobal(rect.bottomLeft())).y()
        w, h = self.width(), self.height()
        x = top.x() - w // 2
        y = top.y() - h - 6
        if y < 0:
            y = bottom + 6                       # 上に入らなければ下へ反転
        x = max(0, min(x, max(0, parent.width() - w)))
        y = max(0, min(y, max(0, parent.height() - h)))
        self.move(x, y)

    # ---------- state ----------
    def sync_state(self) -> None:
        ed = self._editor
        if ed is None or self._syncing:
            return
        self._syncing = True
        try:
            fmt = ed._probe_format()
            va = fmt.verticalAlignment()
            tl = _selected_blocks(ed.textCursor())[0].textList()
            style = tl.format().style() if tl is not None else None
            state = {
                "toggle_bold": fmt.fontWeight() >= QFont.Weight.DemiBold,
                "toggle_italic": fmt.fontItalic(),
                "toggle_underline": fmt.fontUnderline(),
                "toggle_strike": fmt.fontStrikeOut(),
                "toggle_superscript": va == _SUPER,
                "toggle_subscript": va == _SUB,
                "toggle_bullet_list": style == QTextListFormat.Style.ListDisc,
                "toggle_numbered_list": style == QTextListFormat.Style.ListDecimal,
            }
            for name, on in state.items():
                self._buttons[name].setChecked(bool(on))
        finally:
            self._syncing = False

    def _run(self, name: str) -> None:
        ed = self._editor
        if ed is None or self._syncing:
            return
        getattr(ed, name)()
        self.sync_state()
        self.reposition()

    def apply_font(self, font: QFont) -> None:
        # ボタン個別に setFont すると QSS の text-decoration と競合するので、
        # 親フレームにだけ設定して継承させる。
        self.setFont(font)
        self.adjustSize()


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
        self.content = RichTextEdit(
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
        n = len(text.translate(_COUNT_STRIP))
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
        d = {
            "description": self.description.toPlainText(),
            "content": self.content.toPlainText(),
        }
        doc = self.content.document()
        # 書式もソフト改行も無いブロックでは HTML を作らない（v1 とバイト単位で同一になる）。
        if _needs_html(doc):
            # ⚠️ ライブ doc をそのまま toHtml すると (1) 内部編集で付いた block char format
            #    が style= を2つ持つ不正な <li> を生む、(2) StartFragment コメントが再読込で
            #    リストを落とす。clone() を sanitize してから直列化し、マーカーを剥がす。
            #    document().toHtml() はフォントを焼き付けてズームを殺すので使わない（前提4）。
            scratch = doc.clone()
            sanitize_document(scratch, map_margins=False)
            d["content_html"] = _strip_fragment_markers(
                QTextDocumentFragment(scratch).toHtml()
            )
        d["char_limit"] = max(0, limit)
        d["show_count"] = self.cb_show.isChecked()
        return d

    def load_from_dict(self, d: dict) -> None:
        self.description.blockSignals(True)
        self.content.blockSignals(True)
        self.cb_show.blockSignals(True)
        self.ed_limit.blockSignals(True)
        try:
            self.description.setPlainText(str(d.get("description", "")))
            self._load_content(d)
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
        self.content._adjust_height()

    def _load_content(self, d: dict) -> None:
        """content_html があればリッチに、無ければ / 壊れていれば content にフォールバック。"""
        html = d.get("content_html")
        text = str(d.get("content", ""))
        doc = self.content.document()
        doc.setUndoRedoEnabled(False)
        try:
            if isinstance(html, str) and html.strip():
                # ウィジェット側の setHtml を使う（QTextDocument.setHtml は
                # isModified() を True のままにする）。StartFragment コメントは
                # setHtml がリスト所属を落とす原因になるので剥がしてから通す
                # （旧ビルドが保存したファイル・手編集ファイルへの防御）。
                self.content.setHtml(_strip_fragment_markers(html))
                # 読み込み時のサニタイズは必須。前提となるフォント焼き付きと、
                # setHtml が <p> に注入する 12px の段落余白を同時に潰す。
                sanitize_document(doc)
                if not self.content.toPlainText().strip() and text.strip():
                    # 非空文字列でも Qt が空文書に解釈した破損とみなしてやり直す。
                    self.content.setPlainText(text)
            else:
                self.content.setPlainText(text)
        finally:
            doc.setUndoRedoEnabled(True)
        doc.setModified(False)


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
    version = raw.get("version")
    if version not in (1, FILE_VERSION):
        raise ValueError(f"対応していないバージョンです: {version!r}")
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
        item = {
            "description": str(b.get("description", "")),
            "content": str(b.get("content", "")),
            "char_limit": max(0, limit),
            "show_count": bool(b.get("show_count", False)),
        }
        # content_html は文字列のときだけ通す。非文字列はキー欠落と同じ扱いにして
        # content へのフォールバックに落とす。
        html = b.get("content_html")
        if isinstance(html, str):
            item["content_html"] = html
        blocks.append(item)
    return {"version": version, "title": title, "blocks": blocks}


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
        # dirty 判定のデバウンス。入力直後は楽観的に「未保存」を即表示し、
        # タイマ満了時に _snapshot() で確定させる。
        self._dirty_timer = QTimer(self)
        self._dirty_timer.setSingleShot(True)
        self._dirty_timer.setInterval(DIRTY_DEBOUNCE_MS)
        self._dirty_timer.timeout.connect(self._flush_dirty)

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
        # FormatBar とエディタの結び付けは1本に集約する（各エディタから個別に張ると
        # ブロック削除・再読み込みのたびに接続が累積する）。
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

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

        # フローティング書式バー（central widget の子。トップレベルにしない）
        self.format_bar = FormatBar(central)
        self.scroll.verticalScrollBar().valueChanged.connect(
            lambda _v=0: self.format_bar.reposition()
        )

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
        self.format_bar.apply_font(ui)
        self.format_bar.reposition()

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
        self._attach_block(block)
        self._rebuild_tab_order()
        if not initial:
            self._mark_dirty()
            block.content.setFocus()
            self._reveal(block.content)
        return block

    def _attach_block(self, block: BlockWidget) -> None:
        """新しく画面に載せたブロックの配線。add_block / _load_data の共通処理。"""
        block.changed.connect(self._mark_dirty)

    def _destroy_block(self, block: BlockWidget) -> None:
        """ブロック1個の解体。self.blocks には触れない。"""
        # 破棄済みウィジェットへの dangling 参照とシグナル残留を同時に断つ。
        self.format_bar.detach_if(block.content)
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
        # ブロック入れ替えでエディタの画面位置がずれるので、追従させず隠す。
        self.format_bar.hide()
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
        # 楽観的に「未保存」を即表示し、確定判定はデバウンス後に回す。
        if not self.dirty:
            self.dirty = True
            self._update_status()
            self._update_window_title()
        self._dirty_timer.start()

    def _flush_dirty(self) -> None:
        """デバウンスされた dirty 判定を確定させる（Undo で保存状態へ戻れば「保存済み」に戻す）。"""
        self._dirty_timer.stop()
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
        # 片道ドアを避ける: どのブロックも書式を使っていなければ version 1 を書き、
        # 今までのビルドでも開けるようにする。
        blocks = [b.to_dict() for b in self.blocks]
        version = FILE_VERSION if any("content_html" in b for b in blocks) else 1
        return {
            "version": version,
            "title": self.title_edit.text(),
            "blocks": blocks,
        }

    def _load_data(self, data: dict) -> None:
        self._dirty_timer.stop()
        self.format_bar.detach()
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
                self._attach_block(block)
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
        # 古い楽観値でダイアログを出さないよう、ここで同期的に再判定する。
        self._flush_dirty()
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
        self._dirty_timer.stop()
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
        self.format_bar.reposition()

    def action_insert_en_dash(self) -> None:
        w = QApplication.focusWidget()
        if isinstance(w, (QPlainTextEdit, QTextEdit)):
            cursor = w.textCursor()
            cursor.insertText(EN_DASH)
        elif isinstance(w, QLineEdit):
            w.insert(EN_DASH)

    # ---------- events ----------
    def _on_focus_changed(self, _old, new) -> None:
        if isinstance(new, RichTextEdit):
            self.format_bar.attach(new)
        else:
            self.format_bar.detach()

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
        if ev.type() in (QEvent.Type.Resize, QEvent.Type.Move) and obj is self:
            self.format_bar.reposition()
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
