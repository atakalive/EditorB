"""assets/editorb.ico を生成する開発用スクリプト（一度だけ実行すればよい）。

依存は PySide6 のみ（DESIGN.md「技術スタック」を守る。Pillow は使わない）。
各サイズを QPainter で描いて PNG バイト列にし、ICO コンテナ
（ICONDIR + ICONDIRENTRY × n + PNG ペイロード）を struct で自前に組む。
Vista 以降は全サイズで PNG 埋め込みが読めるので BMP 変換は不要。
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "editorb.ico"
SIZES = (16, 32, 48, 64, 128, 256)

# editor.py の QSS に実在する既存カラー
BG = "#1e1e1e"
BAR = "#e0e0e0"
ACCENT = "#3a5a73"


def _render(size: int) -> bytes:
    """size×size のアイコン画像を描いて PNG バイト列を返す。"""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)

    # 角丸背景
    p.setBrush(QColor(BG))
    radius = size * 0.18
    p.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    # ブロックを表す横バー 3 本（真ん中をアクセント色に）
    margin = size * 0.20
    bar_w = size - margin * 2
    bar_h = size * 0.10
    gap = size * 0.11
    total = bar_h * 3 + gap * 2
    y = (size - total) / 2
    bar_r = bar_h * 0.35
    for i in range(3):
        p.setBrush(QColor(ACCENT if i == 1 else BAR))
        p.drawRoundedRect(QRectF(margin, y, bar_w, bar_h), bar_r, bar_r)
        y += bar_h + gap

    p.end()

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def main() -> int:
    QGuiApplication([])  # QPainter を使うために必要

    pngs = [_render(s) for s in SIZES]
    n = len(pngs)

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, n)  # ICONDIR: reserved, type=1(ICO), count
    offset = 6 + 16 * n
    for size, png in zip(SIZES, pngs):
        dim = 0 if size >= 256 else size  # 256px は 0 と書くのがフォーマットの規約
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    for png in pngs:
        out += png

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bytes(out))
    print(f"wrote {OUT} ({len(out)} bytes, {n} images: {', '.join(map(str, SIZES))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
