# Grape / Melon ハードウェア設計判断

作成日: 2026-08-12

この文書は、Cherryを基準にGrapeおよびMelonの回路図・基板を設計する前に固定した
ハードウェア要件である。対象デバイスはGrapeが`XC7S50-1CSGA324C`、Melonが
`XC7A100T-1FGG676C`である。

## 調査資料

取得したAMD公式資料は[`../parts/amd/`](../parts/amd/)に保存した。

- DS180: 7 Series FPGAs Overview
- DS181: Artix-7 DC and AC Switching Characteristics
- UG470: 7 Series FPGAs Configuration User Guide
- UG475: 7 Series FPGAs Packaging and Pinout
- UG483: 7 Series FPGAs PCB Design Guide
- GrapeのSpartan-7電気特性は[DS189](https://docs.amd.com/r/en-US/ds189-spartan-7-data-sheet)
  revision 1.11も参照する。
- QSPIフラッシュは[`../parts/W25Q128JV.pdf`](../parts/W25Q128JV.pdf)を参照する。

回路図のピン割当を確定する際は、UG475の概略図だけでなく対象デバイス・パッケージの
公式ASCII package pin fileと照合する。Grapeの既存`board/pinout.csv`は照合元を明記して
再生成し、Melonにも同じ生成・検査手順を用いる。

## 固定する構成

### 電源

- USB VBUSから`1.0 V`（VCCINT/VCCBRAM）、`1.8 V`（VCCAUX）、`3.3 V`
  （VCCO）を生成する。
- 推奨投入順序は`VCCINT/VCCBRAM`、`VCCAUX`、`VCCO`、切断時は逆順とする。
- 全GPIOバンクは3.3 V HR I/Oとして用いる。Bank 0も3.3 Vとし、`CFGBVS`は
  `VCCO_0`へ接続する。Master SPIで使うBank 14/15もコンフィグ時の電圧整合を取る。
- 各レールの容量、過渡応答、起動時間、FPGA直下のデカップリング配置は、最終I/O
  トグル率を入力した電力見積り後に確定する。Grape旧回路のレギュレーター定格を
  Melonへ無条件にコピーしない。
- Grapeは4層を最低構成、MelonのFGG676は電源島とBGA escapeの都合から6層以上を
  初期案とし、4層へ縮小しない。

### コンフィグレーションとブート

- モードはMaster SPI x4、フラッシュは128 Mbit以上とする。
- アドレス0に書換え保護した`boot`（AMD文書でいうgolden image）を置く。
- 電源投入時は常に`boot`をコンフィグレーションする。`boot`がUSB Full-Speed CDC
  デバイスとして列挙し、ユーザーイメージの検査・書込みを行う。
- userを起動するときは`boot`内の`ICAPE2`から`WBSTAR`へuser先頭アドレスを書き、
  `IPROG`を発行する。userのコンフィグレーション失敗時はアドレス0のbootへ
  fallbackする。
- 裏面に`DEFAULT_USER`はんだジャンパーを置く。オープンはboot待機、ブリッジは
  bootがUSB D+プルアップを有効にする前に検査済みuserへ進む。これは7-seriesの
  モードピンではなく、bootコンフィグレーション後に読む専用GPIOである。
- `DEFAULT_USER`をブリッジしていてもboot自体は最初に必ずロードされる。復旧のため、
  userマニフェスト不正時と指定ボタン押下時はbootに留まる。
- bootとuserは同じUSB VID/PID、descriptorおよびCDC endpoint構成を使う。切替え前に
  USBを論理切断し、user起動後に再列挙する。
- `PROGRAM_B`は4.7 kΩ以下でpull-upし、押しボタンとJTAGヘッダーへ出す。
  `INIT_B`も4.7 kΩ以下でpull-upする。`DONE`、`INIT_B`は状態確認できるようにする。
- `PROGRAM_B`を電源投入時からLowに保持してコンフィグを止める設計にはしない。
  UG470の指定どおり、必要なら`INIT_B`で初期化後の進行を止める。
- JTAG、QSPI、PROGRAM_B、GND、3.3 Vを復旧用ヘッダーまたはテストパッドへ出す。

### クロック

- GrapeおよびMelonの外部基準クロックをCherryと同じ48 MHzには固定しない。
- USB Full-Speed PHY/プロトコル処理に必要なクロックドメインは、外部基準クロックから
  FPGA内蔵MMCM/PLLで生成する。生成可能な周波数、VCO範囲、入力ジッタ、起動・lock時間を
  実装前に確認する。
- 外部発振器はGrapeとMelonで個別に選定できる。位相配列出力の時間分解能、DSP処理、
  クロック対応ピン、ジッタ、消費電力、部品入手性を比較して周波数を決める。
- 発振器は対象bankのclock-capable inputへ接続し、単端／差動方式とI/O電圧は選定部品に
  合わせる。XDCには入力クロック周期と生成クロックを明記する。
- bootとuserは同じ外部発振器設定およびUSBクロック生成条件を共有する。

### GPIOヘッダー

- Cherryと同じ2列2.54 mmヘッダーを用い、GPIO 8本を連続した`2x4`窓にする。
- 各グループは内列4本、対向する外列4本とし、グループ間に内列GND／外列3.3 Vの
  電源位置を置く。コネクター端にもGND、3.3 V、必要な5 Vを置く。
- Grapeは16グループ、合計128 GPIO、Melonは32グループ、合計256 GPIOとする。
- 1グループを可能な限り同一I/O bankに収める。差動対は対向ピンへ分断せず、クロック
  capable pin、VREF、コンフィグ兼用ピンを先に予約する。
- 初期XDCは`LVCMOS33`、`DRIVE 4`、`SLEW SLOW`とし、128/256本同時スイッチングを
  想定したSSO確認なしに駆動力やslewを上げない。

## 現行ファイルの扱い

Grapeの現行回路図は`XC7A35T-1FTG256C`用であり、目的のSpartan-7 CSGA324回路として
製造してはならない。現行PCBは部品配置のみで、配線、via、plane、zoneがない。
新しい回路図へ移行後、ネットリストから基板を作り直す。

Melonはまだボードディレクトリがないため、Grapeの完成済み共通ブロックをテンプレートに
する。ただしFGG676の電源ピン、bank構成、BGA escape、デカップリングは専用設計にする。

## 完了条件

回路図・基板を「完成」とする条件は次のとおり。

1. 公式package pin fileとの全BGA ball自動照合
2. KiCad ERCエラー0（意図した例外は文書化）
3. 全GPIO、USB、QSPI、JTAG、電源ネットのnetlist検査
4. PCB上の未配線0、DRCエラー0
5. 電源plane、帰路、差動USB、クロック、QSPIの配線レビュー
6. 電源・熱・SSO見積りと、レギュレーター起動順序の確認
7. 製造用出力とは別に回路図PDF、基板表裏PDF、BOM、pinout、XDCを生成
