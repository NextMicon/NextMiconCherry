# 基板環境構築ガイド

Cherry は FPGA 開発ボードプロジェクトです。基板設計には KiCad を使用します。

## 1. Install KiCad

```bash
$ wget https://downloads.kicad.org/kicad/linux/explore/stable/download/kicad-10.0.0-x86_64.AppImage.tar
$ tar xf kicad-10.0.0-x86_64.AppImage.tar
$ chmod +x kicad-10.0.0-x86_64.AppImage
$ sudo mv kicad-10.0.0-x86_64.AppImage /opt/kicad
$ /opt/kicad --version
10.0.0
```

## 2. Open KiCad project

```
$ /opt/kicad src/cherry.kicad_pro
```

```
cherry/
├── src/         # KiCad プロジェクト
├── doc/         # ドキュメント
├── lib/         # カスタムシンボル・フットプリント
├── datasheets/  # 部品のデータシート
└── README.md
```

## 3. 次のステップ

1. FPGA チップの選定 (Lattice iCE40, Gowin, Xilinx Artix-7 等)
2. 回路図設計 (電源回路、クロック、コンフィグレーション、I/O)
3. 基板レイアウト設計
4. ガーバー出力・発注
