# NextMicon Cherry firmware

Native USB management, boot, flash, and runtime HDL for the iCE40HX8K-BG121.

## USB transport

Every image enumerates as one CDC ACM serial device with the same endpoint
layout:

| Purpose | Endpoint | Transfer |
| --- | --- | --- |
| CDC notification | EP1 IN (`0x81`) | Interrupt |
| CDC serial host-to-FPGA | EP2 OUT (`0x02`) | Bulk |
| CDC serial FPGA-to-host | EP2 IN (`0x82`) | Bulk |

The CDC byte stream carries COBS-delimited frames. A channel byte inside each
frame selects BOOT, FLASH, or UART, so arbitrary UART data is never scanned for
a reboot escape sequence. The protected `boot` image reports BOOT and FLASH
capabilities; the writable `user` image reports BOOT and UART capabilities.

The protocol constants are in `src/protocol.veryl` and the complete wire
format is documented in [`doc/flash.md`](../../../doc/flash.md).

The current code defines the shared constants, endpoint policy, and final
warm-boot request controller. The USB physical engine, CDC standard/class
request handler, COBS frame codec, flash commands, and UART FIFOs remain to be
implemented.
