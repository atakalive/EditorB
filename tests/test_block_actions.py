"""ブロックのタイトル＋本文コピー（`BlockWidget.block_mime` / `_copy_block_of`）の単体テスト。

`block_mime` はクリップンボードに触れない純粋な組み立てなので headless で検証できる。
特に「本文先頭が箇条書きでもタイトルが箇条書き項目化されない」回帰（新規 doc ＋
insertFragment 方式）を固定する。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import editor  # noqa: E402

# BlockWidget の生成には QApplication が要る。プロセス内で1つだけ用意する。
_app = QApplication.instance() or QApplication([])


def _iter_blocks(doc: QTextDocument):
    b = doc.begin()
    while b.isValid():
        yield b
        b = b.next()


def test_plain_and_rich() -> None:
    block = editor.BlockWidget()
    block.description.setPlainText("見出し行")
    block.content.setHtml("<p>これは<b>太字</b>です</p>")

    mime = block.block_mime()

    # プレーンはタイトル＋空行＋本文（各 rstrip）。
    assert mime.text() == "見出し行\n\nこれは太字です"
    # リッチ側はタイトル・本文・太字書式を保持する。
    html = mime.html()
    assert "見出し行" in html
    assert "太字" in html
    assert "font-weight" in html


def test_title_not_listified() -> None:
    """本文先頭が箇条書きでも、タイトルは箇条書き項目にならない（バグ回帰）。"""
    block = editor.BlockWidget()
    block.description.setPlainText("見出し行")
    block.content.setHtml("<ul><li>項目1</li><li>項目2</li></ul>")

    mime = block.block_mime()

    d = QTextDocument()
    d.setHtml(mime.html())
    blocks = list(_iter_blocks(d))
    title_blocks = [b for b in blocks if b.text() == "見出し行"]
    assert title_blocks, "タイトル段落が見つからない"
    # タイトルはリスト項目化されていない。
    assert all(b.textList() is None for b in title_blocks)
    # 本文側のリストは残る。
    assert any(b.textList() is not None for b in blocks)


def test_title_only_and_body_only() -> None:
    # 本文だけ（タイトル空）。
    b1 = editor.BlockWidget()
    b1.content.setPlainText("本文のみ")
    assert b1.block_mime().text() == "本文のみ"

    # タイトルだけ（本文空）。
    b2 = editor.BlockWidget()
    b2.description.setPlainText("タイトルのみ")
    assert b2.block_mime().text() == "タイトルのみ"


def test_copy_writes_clipboard() -> None:
    block = editor.BlockWidget()
    block.description.setPlainText("題")
    block.content.setPlainText("中身")

    QApplication.clipboard().setText("SENTINEL")
    editor._copy_block_of(block.content)
    assert QApplication.clipboard().text() == "題\n\n中身"


def test_empty_block_does_not_overwrite_clipboard() -> None:
    block = editor.BlockWidget()  # 空のまま

    QApplication.clipboard().setText("SENTINEL")
    editor._copy_block_of(block.content)
    # 空ブロックはクリップボードを上書きしない。
    assert QApplication.clipboard().text() == "SENTINEL"
