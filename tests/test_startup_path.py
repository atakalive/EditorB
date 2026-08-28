"""`_startup_path` の契約を固定する単体テスト。

本 Issue で追加された唯一の純ロジックが `_startup_path`。GUI / registry 系は
手動検証に委ねるが、引数選択の契約（拡張子選択・ハイフン始まりファイル名・
値付きオプション読み飛ばし・大小無視・相対→絶対）は回帰に弱いのでここで固定する。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# QApplication は生成しないが、念のため import 時点で表示に依存しないようにしておく。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import editor  # noqa: E402

EXT = editor.FILE_EXT  # ".editorb"


def test_absolute_path_returned_resolved() -> None:
    p = Path.cwd() / f"sample{EXT}"
    assert editor._startup_path([str(p)]) == p.resolve()


def test_relative_path_is_resolved_to_absolute() -> None:
    got = editor._startup_path([f"sample{EXT}"])
    assert got is not None
    assert got.is_absolute()
    assert got == Path(f"sample{EXT}").resolve()


def test_hyphen_leading_filename_is_picked() -> None:
    # '-' で始まる正当なファイル名を取りこぼさない
    got = editor._startup_path([f"-draft{EXT}"])
    assert got == Path(f"-draft{EXT}").resolve()


def test_value_taking_option_value_is_skipped() -> None:
    # `-style Fusion plan.editorb` の Fusion をファイル名と誤認しない
    got = editor._startup_path(["-style", "Fusion", f"plan{EXT}"])
    assert got == Path(f"plan{EXT}").resolve()


def test_extension_match_is_case_insensitive() -> None:
    got = editor._startup_path(["Proposal.EDITORB"])
    assert got == Path("Proposal.EDITORB").resolve()


def test_first_editorb_argument_wins() -> None:
    got = editor._startup_path([f"a{EXT}", f"b{EXT}"])
    assert got == Path(f"a{EXT}").resolve()


def test_no_editorb_argument_returns_none() -> None:
    assert editor._startup_path([]) is None
    assert editor._startup_path(["-style", "Fusion"]) is None
    assert editor._startup_path(["notes.txt"]) is None
