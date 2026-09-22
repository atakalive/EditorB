"""文字数カウントの太字表示（超過時）の契約を固定する単体テスト。

超過時は黄色ではなく太字にする。太字はリッチテキスト `<b>` をラベルの text に
埋め込むことで実現している（QSS の font-weight / setFont はズーム時の setFont 再適用で
失われるため）。

⚠️ offscreen プラットフォームは合成太字を一切「描画」しないので、grab したピクセルで
太字を検証してはいけない（過去これで誤検証した）。ここでは描画に依存せず、
`lbl_count.text()` に `<b>` が入るか否かという純粋な状態だけを固定する。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

import editor  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _make_block(limit: str, text: str) -> "editor.BlockWidget":
    b = editor.BlockWidget()
    b.cb_show.setChecked(True)
    b.ed_limit.setText(limit)
    b.content.setPlainText(text)
    b._refresh_counter()
    return b


def test_over_limit_is_bold() -> None:
    # 上限3・本文4文字 → 超過。太字（<b>）で表示する。
    b = _make_block("3", "abcd")
    assert b.lbl_count.text() == "<b>4</b>"


def test_under_limit_is_plain() -> None:
    # 上限3・本文2文字 → 未満。素の数字（太字なし）。
    b = _make_block("3", "ab")
    assert b.lbl_count.text() == "2"


def test_no_limit_is_plain() -> None:
    # 上限0（未設定）なら超過扱いにしない。
    b = _make_block("0", "abcdef")
    assert b.lbl_count.text() == "6"


def test_hidden_when_show_unchecked() -> None:
    # 文字数表示 OFF なら従来通り隠す。
    b = editor.BlockWidget()
    b.cb_show.setChecked(False)
    b.content.setPlainText("abcd")
    b._refresh_counter()
    assert b.lbl_count.isHidden()
