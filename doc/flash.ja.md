# CDCフラッシュ・プロトコル

[English](flash.md)

この文書はNextMicon CherryのFPGAイメージ、ホストツール`nmb`、Web Serial
アプリケーションで共通に使用するシリアル・フレーム、ブート管理、フラッシュ書き込み、
ユーザーデータ・チャンネルを定義します。マルチブート手順とフラッシュ配置は
[boot.ja.md](boot.ja.md)を参照してください。

`flash/cli`のRustホストと`flash/web`の静的Web Serialアプリケーションは本プロトコルを
実装済みです。Cherry HDLのCDC ACM USBエンジンとフレーム処理はまだ未実装です。

## トランスポート方式

すべてのイメージが同一のUSB CDC ACMシリアルデバイスとして列挙されます。BOOT、FLASH、
UARTはフレーム化されたシリアル・バイトストリーム内の論理チャンネルであり、個別のUSB
エンドポイントではありません。これにより、ネイティブアプリケーションはOS標準の
シリアルドライバーを使用でき、対応ブラウザではWeb Serialから書き込めます。

ストリームは常にフレーム化します。ユーザーUARTデータもUARTチャンネルのpayloadとして
運び、再起動用エスケープシーケンスを検索しません。

## USB CDC ACMプロファイル

CherryはUSB VBUSから給電されるUSB 2.0 Full-Speedデバイスです。48 MHzのFPGAクロックを
使用し、12 Mbit/sで動作します。

| 用途                     | インターフェース／EP | 転送形式  | 最大パケット |
| ------------------------ | -------------------- | --------- | -----------: |
| 標準／CDCリクエスト      | EP0                  | Control   |     64バイト |
| CDC通知                  | EP1 IN `0x81`        | Interrupt |     16バイト |
| CDCシリアル・ホスト→FPGA | EP2 OUT `0x02`       | Bulk      |     64バイト |
| CDCシリアル・FPGA→ホスト | EP2 IN `0x82`        | Bulk      |     64バイト |

CDC機能はCommunication ClassインターフェースとData Classインターフェースを1個ずつ持ち、
Header、Call Management、ACM、Union Functional Descriptorを含みます。少なくとも次を
実装します。

- USB列挙とエンドポイントHALT復旧に必要な標準リクエスト
- `SET_LINE_CODING`と`GET_LINE_CODING`
- `SET_CONTROL_LINE_STATE`
- EP1 INによるCDC `SERIAL_STATE`通知

ホストの公称設定は115200 baud、8 data bits、no parity、1 stop bitです。同期USB
ストリームなのでbaud rateは実際の転送速度を制御しません。DTR、RTS、baud rate変更、
BREAKをイメージ選択やフラッシュ消去に使用してはいけません。

### 不変のデバイス識別情報

`boot`と`user`は同じVID、PID、Manufacturer、Product、Serial Numberを使用します。実行中の
イメージと利用可能機能はフレーム化GET_INFOコマンドで取得します。同じUSB識別情報を使う
ことで、FPGA再コンフィグレーションをまたぐOSとWeb Serialの権限処理を簡単にします。

| 文字列        | 値／要件                   |
| ------------- | -------------------------- |
| Manufacturer  | `NextMicon`                |
| Product       | `NextMicon Cherry`         |
| Serial Number | 物理基板ごとに一意かつ不変 |

製品用VID/PIDは未割当です。サンプル値や他製品のIDを使用したまま出荷してはいけません。
割当完了までは`nmb`がManufacturer／Product文字列から検出でき、
`--usb-id VID:PID`で明示的に限定できます。

選択イメージのUSB初期化が終わるまでD+プルアップを無効にします。ウォームブートでは応答
フレームとCDC IN転送を完了し、D+プルアップを無効にして再コンフィグレーションした後、
同じ識別情報で再列挙します。

## ワイヤ・フレーム

各メッセージをCOBSでエンコードし、末尾へ`0x00`を1バイト付けます。

```text
COBS(decoded frame) 00
```

COBSデータ内にはゼロが現れないため、受信エラー後も次の`0x00`を探してフレーム境界へ
復帰できます。USB readの区切りにプロトコル上の意味はなく、1回のreadにフレームの一部、
または複数フレームが含まれることがあります。

### デコード後のフレーム

| オフセット | サイズ | フィールド                          |
| ---------: | -----: | ----------------------------------- |
|          0 |      1 | プロトコル・バージョン、現在`0x01`  |
|          1 |      1 | チャンネル                          |
|          2 |      1 | オペコード                          |
|          3 |      1 | シーケンス番号                      |
|          4 |      2 | payload長、リトルエンディアン       |
|          6 | 0～256 | payload                             |
|   6+length |      4 | CRC-32/ISO-HDLC、リトルエンディアン |

CRCの対象は6バイトのheaderとpayloadです。CRCフィールド、COBS overhead、末尾delimiterは
除外します。パラメーターは多項式`0x04c11db7`、初期値`0xffffffff`、入出力反転あり、
最終XOR`0xffffffff`です。

| 上限                             |        値 |
| -------------------------------- | --------: |
| 最大payload                      | 256バイト |
| 最大decoded frame                | 266バイト |
| delimiterを含む最大encoded frame | 269バイト |

不正なCOBS、未対応version、length不一致、oversize、CRC不一致のフレームは応答せず破棄し、
次のdelimiterから受信を継続します。

### チャンネル、オペコード、シーケンス

| チャンネル |     値 | `boot` | `user` |
| ---------- | -----: | ------ | ------ |
| BOOT       | `0x01` | 利用可    | 利用可       |
| FLASH      | `0x02` | 利用可    | 利用不可     |
| UART       | `0x03` | 利用不可  | 利用可       |

BOOTとFLASHでは、ホストは一度に1個だけリクエストを送ります。レスポンスは同じチャンネルと
シーケンス番号を持ち、リクエスト・オペコードのbit 7をセットします。

```text
response opcode = request opcode | 0x80
```

シーケンス番号は256でwrapし、古いレスポンスと新しいリクエストの誤対応を防ぎます。
UART DATAはACKなしで、独立してwrapできます。

## BOOTチャンネル`0x01`

### GET_INFO `0x00`

リクエストpayloadは空です。レスポンス・オペコードは`0x80`で、payloadは次の3バイトです。

| オフセット | サイズ | フィールド                |
| ---------: | -----: | ------------------------- |
|          0 |      1 | BOOT status、成功時`0x00` |
|          1 |      1 | 実行中イメージ：`0`（`boot`）または`1`（`user`） |
|          2 |      1 | capability bitmap         |

Capability bitは`0x01` BOOT、`0x02` FLASH、`0x04` UARTです。`boot`は`0x03`、
`user`は`0x05`を返し、予約bitはゼロです。

### SELECT_IMAGE `0x01`

リクエストpayloadは対象イメージの1バイトで、`0`は`boot`、`1`は`user`です。2～255は
不正です。レスポンス・オペコードは`0x81`、payloadはBOOT statusの1バイトです。

| Status | 意味                            |
| -----: | ------------------------------- |
| `0x00` | Accepted                        |
| `0x01` | イメージまたはpayloadが不正     |
| `0x02` | 対象マニフェストまたはCRCが不正 |
| `0x03` | Boot／Flash managerがbusy       |

Acceptedでは、完全なレスポンス・フレームをホストへ送ってからUSBを切断します。その後QSPIを
停止し、永続QPIモードを終了し、フラッシュ`/CS`をHighにして`SB_WARMBOOT`をアサートします。
拒否した場合は現在のイメージを継続します。

## FLASHチャンネル`0x02`

FLASHレスポンスpayloadの先頭は常にstatusです。

| Status | 意味                           |
| -----: | ------------------------------ |
| `0x00` | Accepted／完了                 |
| `0x01` | 不正または利用不可のコマンド   |
| `0x02` | アドレス、長さ、スロットが不正 |
| `0x03` | 書き込み保護領域               |
| `0x04` | Flash／Boot managerがbusy      |
| `0x05` | SPIフラッシュI/O失敗           |

### ERASE_SLOT `0x01`

リクエストpayloadは固定のuserスロット値`1`です。レスポンス・オペコードは`0x81`で、statusを
1バイト返します。成功時は256 KiBのuser領域全体を消去し、WIPクリア後に応答します。
boot領域は常に保護します。

### WRITE `0x02`

| Payload offset | サイズ | フィールド                                       |
| -------------: | -----: | ------------------------------------------------ |
|              0 |      3 | 24ビット・フラッシュアドレス、リトルエンディアン |
|              3 | 1～253 | データ                                           |

レスポンス・オペコードは`0x82`でstatusを1バイト返します。成功時は全データのprogramと
WIPクリア後に応答します。SPI page境界をまたぐ場合はFPGA内部で分割します。USB書き込みは
user（`0x040000-0x07ffff`）に限定し、boot領域はハードウェアで保護します。

### READ `0x03`

| Payload offset | サイズ | フィールド                                       |
| -------------: | -----: | ------------------------------------------------ |
|              0 |      3 | 24ビット・フラッシュアドレス、リトルエンディアン |
|              3 |      2 | 読み出し長、リトルエンディアン（`1`～`255`）     |

レスポンス・オペコードは`0x83`です。payloadはstatus `0x00`と要求したデータで、4 MiBの
メインフラッシュ範囲を越えてはいけません。`nmb`はREADでビットストリームとマニフェスト
全体を検証します。ユーザーデータ領域の消去／書き込みは将来のrevisionへ予約します。

## イメージ・マニフェスト

256 KiBのuser領域の最後の32バイトをマニフェストに使用します。生の
ビットストリームは最大262,112バイトで、マニフェストを最後に書き込みます。

| オフセット | サイズ | フィールド                             |
| ---------: | -----: | -------------------------------------- |
|          0 |      4 | ASCII `NMF1`                           |
|          4 |      1 | Manifest version `1`                   |
|          5 |      1 | userイメージ番号、常に`1`               |
|          6 |      2 | Flags、ゼロ                            |
|          8 |      4 | ビットストリーム長、リトルエンディアン |
|         12 |      4 | CRC-32/ISO-HDLC、リトルエンディアン    |
|         16 |     16 | 予約、すべて`0xff`                     |

Manifest CRCはスロット先頭からbitstream lengthで示すデータだけを対象とし、消去済みpaddingと
manifestは除外します。BOOTはmagic、version、image number、範囲内でゼロでないlength、CRCを
検証してから対象を受理します。

## UARTチャンネル`0x03`

UART DATAのオペコードは`0x01`で、payloadは0～256バイトです。双方向ともACKはありません。
packet／frame境界はユーザー・バイトストリーム上の意味を持たず、順序を維持して暗黙に
破棄してはいけません。FIFOのバックプレッシャーをCDC Bulkエンドポイントまで伝えます。

UARTデータもフレーム化されるため、シリアルターミナルを直接接続することはできません。
ホストconsoleがUARTフレームを付加／除去します。これにより任意のユーザーデータがBOOT
コマンドとして解釈されることを防ぎます。

## `nmb`による書き込み

`nmb`はCDCポートを列挙し、USB IDまたはNextMicon文字列で絞り込み、不変のSerial Numberを
`cherry-<serial>`として使用します。

```sh
nmb ls
nmb boot cherry-0123 user
nmb flash cherry-0123 image.bin --boot
```

書き込み前にGET_INFOを送ります。`user`が動作中なら`boot`を要求し、同じSerial Numberの
再列挙を待ち、GET_INFOで`boot`を確認してからerase、write、manifest、readbackを実行します。
user領域は一意なので書き込み先引数はありません。

## Web Serialによる書き込み

`flash/web`はpnpmで管理するReact／Tailwind CSSアプリケーションです。`nmb`と同じRust
プロトコルライブラリをWebAssemblyへコンパイルし、JavaScriptはWeb Serialトランスポートと
UI状態を管理します。ネイティブUSBドライバーは不要です。ブラウザ要件とAPI動作は
[Web Serial仕様](https://wicg.github.io/serial/)で定義されています。

```js
const port = await navigator.serial.requestPort();
await port.open({ baudRate: 115200, bufferSize: 4096 });
```

Webアプリケーションは次を実行します。

1. `port.readable`の任意サイズのchunkを`0x00`で分割します。
2. 各フレームをRust WASMへ渡し、COBS decodeとCRC確認を行います。
3. channel、response opcode、sequenceで管理レスポンスを対応付けます。
4. File Pickerでローカルのbitstreamを選択します。
5. `nmb`と同じGET_INFO、SELECT_IMAGE、ERASE_SLOT、WRITE、READを実行します。
6. 切断時にreader／writerを閉じ、ウォームブート後の再列挙でportを再度開きます。

依存関係をインストールし、Secure ContextになるlocalhostでViteを起動します。対応する
Chromium系ブラウザで表示されたURLを開きます。

```sh
cd flash/web
pnpm install
pnpm dev
```

`pnpm build`はRust WASMを再生成し、本番用bundleを`flash/web/dist`へ出力します。

### WASM JSON境界

WASMライブラリは`encodeMessageJson`、`decodeMessageJson`、`crc32`を公開します。先頭2関数は
完全なwire frameと次のJSON表現を相互変換します。

```json
{"version":1,"channel":2,"opcode":3,"sequence":7,"payload":[0,0,4,255,0]}
```

すべてのフィールドが必須で、未知のフィールドは拒否します。`payload`はbyte値の配列です。
`encodeMessageJson`は末尾`0x00`を含むCOBS encoded bytesを返します。
`decodeMessageJson`はCOBS、length、version、channel、CRCを検証してからJSONを返すため、
`nmb`とブラウザでwire format検証を共通化できます。

Web Serialは対応ブラウザかつSecure Contextでのみ利用できます。ポート選択には明示的な
ユーザー許可と通常はユーザー操作が必要です。`navigator.serial.getPorts()`から許可済み
ポートを取得できる場合がありますが、切断後に再選択が必要なブラウザ動作も考慮し、Web
flasherは自動アクセスを前提にせず「再接続」操作を表示します。

アプリは許可済みで同じUSB VID/PIDを持つportを最大15秒待ち、GET_INFOで実行中イメージを
確認します。同じUSB識別情報の基板を複数許可している場合、自動再列挙中は書き込み対象の
基板だけを接続してください。

Webページからもデバイス側保護は迂回できません。`boot`は書き込み不可で、FPGAが
アドレスを検証し、書き込んだ全バイトをreadbackします。bitstreamはブラウザ内だけで処理
でき、サーバーへのuploadは不要です。

## 未実装項目

- 製品用USB VID/PID割当と最終Power Descriptor
- FPGAのUSB Full-Speed物理層／packet engine
- CDC ACM descriptor、標準request、notification endpoint
- HDLのCOBS codecとCRC32 frame engine
- HDLのBOOT／FLASH／UART dispatchとFIFO
- `nmb`のフレーム化UART consoleコマンド

これらは本書のフレーム形式とフラッシュ形式を維持して実装します。
