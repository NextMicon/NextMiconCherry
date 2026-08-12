# Cherry Pmod breakout board

Cherryのピンヘッダ(J2/J3/J4)を上から**ピンソケット(S2/S3/S4)に挿し込み**、全64本のGPIOを8ポートのPmod(2×6、12ピン)として引き出すブレークアウト基板です。工場テスト(factory-test.sh)と、Pmodモジュールを挿しての動作確認の両方に使えます。

## ポート構成

| ポート | GPIO | 位置 |
| ------ | ---------- | -------- |
| PMOD1  | GPIO_1-8   | 下辺 左 |
| PMOD2  | GPIO_9-16  | 下辺 中左 |
| PMOD3  | GPIO_17-24 | 下辺 中右 |
| PMOD4  | GPIO_25-32 | 下辺 右 |
| PMOD5  | GPIO_33-40 | 上辺 右 |
| PMOD6  | GPIO_41-48 | 上辺 中右 |
| PMOD7  | GPIO_49-56 | 上辺 中左 |
| PMOD8  | GPIO_57-64 | 上辺 左 |

Cherry側のGPIOはブロック対配置(D0-D3が内側列、D4-D7がその対向の外側列)なので、各Pmodポートは Cherry の1つの2×4ブロックにそのまま対応します。各ポートのピン配置はPmod標準どおり: 1-4 = D0-D3、5 = GND、6 = 3V3、7-10 = D4-D7、11 = GND、12 = 3V3。D0が各ブロックの最小GPIO番号です(例: PMOD5のD0 = GPIO_33)。Pmodソケットは2×6のライトアングル・メスを基板端向きに実装します(実装前にピン1の向きをシルクの角パッドで確認してください)。

- S2/S3: 2×24ピンソケット。Cherry J2/J3が挿さります(ソケットのピン番号 = Cherryのパッド番号)。
- S4: 1×6ピンソケット。Cherry J4が挿さります。
- J5: Cherry J4のSPI/CRESET/GNDを引き出す1×6ピンヘッダ(右辺)。
- J6: +5V / +3V3 / GND / CRESET_B のユーティリティ、1×6ピンヘッダ(左辺)。
- USB-CはCherry本体へ直接接続します。基板にはUSB回路を載せません。
- F.Fabレイヤの破線はCherry外形、MH1--MH4はM3スタンドオフ用です。

電源はGND(裏面ベタ)と+3V3(表面ベタ)のゾーンで配電し、Cherryの全GND/3V3ピンとPmodの電源ピンを共通ネットに接続しています。GPIOと SPI/CRESET は1:1配線です。ソケットピンと引き出し先の対応は[`pinmap.csv`](pinmap.csv)を参照してください(`fixture_ref`はソケット:パッド番号、`dut_pin`はコネクタ位置1..24、`breakout_pin`は引き出し先)。

[`src/fixture.kicad_pcb`](src/fixture.kicad_pcb)は[`tools/gen_fixture.py`](tools/gen_fixture.py)で生成しています(配線・ゾーン込み。再生成後は pcbnew Python でゾーンを塗り直してください)。座標や割当を変えるときは手編集せずスクリプトを直して再生成してください。
