"""`.editorb` を HKCU に関連付ける（管理者権限不要）。

    python tools/register_filetype.py              登録
    python tools/register_filetype.py --unregister 解除

登録は HKEY_CURRENT_USER\\Software\\Classes 配下のみを触る。
`EditorB.Document` は EditorB 専用 ProgID なので丸ごと所有するが、
共有キーである `.editorb` は既存値を壊さず加算的に扱う。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if sys.platform != "win32":
    sys.exit("このスクリプトは Windows 専用です。")

import ctypes
import winreg

PROGID = "EditorB.Document"
EXT = ".editorb"
CLASSES = r"Software\Classes"
EXT_KEY = rf"{CLASSES}\{EXT}"
PROGID_KEY = rf"{CLASSES}\{PROGID}"
OPENWITH_KEY = rf"{EXT_KEY}\OpenWithProgids"
PREV_VALUE = "PrevDefaultProgID"
FILEEXTS = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{EXT}"
SHCNE_ASSOCCHANGED = 0x08000000

ROOT = Path(__file__).resolve().parent.parent


def _find_pythonw() -> Path:
    cand = Path(sys.executable).with_name("pythonw.exe")
    if cand.exists():
        return cand
    for base in (Path(sys.base_prefix), Path(sys.base_prefix) / "Scripts"):
        c = base / "pythonw.exe"
        if c.exists():
            return c
    sys.exit("pythonw.exe が見つかりません。ベース Python のインストール先を確認してください。")


def _verify_pyside6(pyw: Path) -> None:
    """pyw で PySide6.QtWidgets を import できなければ登録を中止する（無言死の回避）。"""
    r = subprocess.run(
        [str(pyw), "-c", "import PySide6.QtWidgets"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(
            f"選定した interpreter で PySide6 を import できません:\n  {pyw}\n"
            f"このまま登録するとダブルクリックが無言で失敗します。中止します。\n"
            f"（{pyw} に PySide6 を入れるか、EditorB を動かせる Python から実行してください）\n"
            f"--- stderr ---\n{r.stderr}"
        )


def _delete_tree(root, path: str) -> None:
    """path 以下を葉から再帰削除する。存在しなければ no-op。"""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)  # 削除で index がずれるので常に 0 を取る
                except OSError:
                    break
                _delete_tree(k, sub)  # 開いたハンドルを親として相対キーを再帰削除
    except FileNotFoundError:
        return
    winreg.DeleteKey(root, path)


def _read_default(path: str) -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            v, _ = winreg.QueryValueEx(k, "")
            return v
    except (FileNotFoundError, OSError):
        return None


def _set(path: str, name: str, value: str) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def _notify() -> None:
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)


def _report_existing() -> None:
    """UserChoice / OpenWithList の残骸を報告する（削除はしない）。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{FILEEXTS}\UserChoice") as k:
            progid, _ = winreg.QueryValueEx(k, "ProgId")
        print(
            f"\n[注意] UserChoice が存在します（ProgId={progid}）。\n"
            f"  HKCU\\{FILEEXTS}\\UserChoice\n"
            "  これはレジストリ登録より優先されます。エクスプローラーで .editorb を右クリック →\n"
            "  「プログラムから開く」→「別のプログラムを選択」で EditorB を選び直してください。"
        )
    except (FileNotFoundError, OSError):
        print("\nUserChoice は存在しません（登録がそのまま効きます）。")

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{FILEEXTS}\OpenWithList") as k:
            n_sub, n_val, _ = winreg.QueryInfoKey(k)
            items = []
            for i in range(n_val):
                name, val, _ = winreg.EnumValue(k, i)
                items.append(f"{name}={val}")
            if items:
                print(
                    f"\n[情報] OpenWithList に既存項目があります: {', '.join(items)}\n"
                    f"  HKCU\\{FILEEXTS}\\OpenWithList\n"
                    "  関連付け自体は阻害しませんが「プログラムから開く」一覧に残ります。\n"
                    "  気になる場合は上記キーから手動で削除してください。"
                )
    except (FileNotFoundError, OSError):
        pass


def register() -> None:
    pyw = _find_pythonw()
    _verify_pyside6(pyw)
    command = f'"{pyw}" "{ROOT / "editor.py"}" "%1"'
    icon = f"{ROOT / 'assets' / 'editorb.ico'},0"  # 引用符なし・末尾 ,0

    print(f"pythonw : {pyw}")
    print(f"command : {command}")
    print(f"icon    : {icon}")

    # 1. EditorB.Document ツリー（自前所有）。in-place 上書き（PrevDefaultProgID を失わない）
    _set(PROGID_KEY, "", "EditorB 文書")
    _set(rf"{PROGID_KEY}\DefaultIcon", "", icon)
    _set(rf"{PROGID_KEY}\shell\open", "FriendlyAppName", "EditorB")
    _set(rf"{PROGID_KEY}\shell\open\command", "", command)

    # 2. .editorb（共有キー・非破壊）
    prev = _read_default(EXT_KEY)
    if prev and prev != PROGID:
        _set(PROGID_KEY, PREV_VALUE, prev)
        print(f"既存の既定 ProgID '{prev}' を {PROGID}\\{PREV_VALUE} に退避しました。")
    _set(EXT_KEY, "", PROGID)
    _set(OPENWITH_KEY, PROGID, "")

    _notify()
    print(f"\n{EXT} を {PROGID} に関連付けました（HKCU）。")
    _report_existing()


def unregister() -> None:
    # 1. .editorb の復元（既定値が EditorB.Document のときだけ触る）
    cur = _read_default(EXT_KEY)
    if cur == PROGID:
        prev = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROGID_KEY) as k:
                prev, _ = winreg.QueryValueEx(k, PREV_VALUE)
        except (FileNotFoundError, OSError):
            prev = None
        if prev:
            _set(EXT_KEY, "", prev)
            print(f"{EXT} の既定 ProgID を '{prev}' に復元しました。")
        else:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, EXT_KEY, 0, winreg.KEY_ALL_ACCESS
                ) as k:
                    winreg.DeleteValue(k, "")
            except (FileNotFoundError, OSError):
                pass
    elif cur:
        print(f"{EXT} の既定 ProgID は '{cur}'（EditorB 以外）のため触りません。")

    # OpenWithProgids から自分の値だけ削除し、空になったらキーごと削除
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, OPENWITH_KEY, 0, winreg.KEY_ALL_ACCESS
        ) as k:
            try:
                winreg.DeleteValue(k, PROGID)
            except FileNotFoundError:
                pass
            n_sub, n_val, _ = winreg.QueryInfoKey(k)
        if n_sub == 0 and n_val == 0:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, OPENWITH_KEY)
    except (FileNotFoundError, OSError):
        pass

    # 2. EditorB.Document ツリー（自前所有）は葉から再帰削除
    _delete_tree(winreg.HKEY_CURRENT_USER, PROGID_KEY)

    # 3. .editorb が空になった場合のみ削除
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, EXT_KEY) as k:
            n_sub, n_val, _ = winreg.QueryInfoKey(k)
        if n_sub == 0 and n_val == 0:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, EXT_KEY)
            print(f"{EXT} キーが空になったため削除しました。")
        else:
            print(f"{EXT} キーには他の値／サブキーが残っているため残します。")
    except (FileNotFoundError, OSError):
        pass

    _notify()
    print(f"\n{PROGID} の登録を解除しました。")


def main() -> int:
    if "--unregister" in sys.argv[1:]:
        unregister()
    else:
        register()
    return 0


if __name__ == "__main__":
    sys.exit(main())
