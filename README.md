# EditorB

シンプルなブロック式テキストエディタ。
項目ごとに文字数の上限がある文書を書くためのもの。

- 文書を「項目の説明」と「本文」のブロックに分けて書く
- ブロックごとに文字数を数え、上限を超えると表示で知らせる
- 操作はほぼキーボードショートカットだけ
- 余計な機能はなく、書くことに集中できる

## 動作環境

- Windows
- Python 3 と PySide6

## 使い方

```
pip install -r requirements.txt
run.bat
```

`python editor.py` でも起動できる。保存形式は JSON（拡張子 `.editorb`）。

`register.bat` を実行すると `.editorb` ファイルをダブルクリックで開けるようになる（管理者権限は不要）。解除は `unregister.bat`。

### Mac・Linux

bat ファイルは使えないので、次のように直接起動する。（動作未確認）

```
pip3 install -r requirements.txt
python3 editor.py
```

## 主なショートカット

| キー | 動作 |
|---|---|
| Ctrl+S / Ctrl+Shift+S | 保存 / 名前を付けて保存 |
| Ctrl+O / Ctrl+N | 開く / 新規作成 |
| Ctrl+E | Markdown / テキストへ書き出し |
| Ctrl+Shift+Insert | ブロックを挿入 |
| Ctrl+Shift+Delete | ブロックを削除 |
| Ctrl+Shift+Up / Down | ブロックを上下に移動 |
| Ctrl+ホイール / Ctrl++ / Ctrl+0 | 文字サイズの変更 / 元に戻す |
| Ctrl+B / Ctrl+I / Ctrl+U | 太字 / 斜体 / 下線 |

ほかの操作と詳しい仕様は [DESIGN.md](DESIGN.md) にある。

## ライセンス

[MIT](LICENSE)
