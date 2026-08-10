# NextMicon Cherry HDL

Native USB management and runtime blocks for the iCE40HX8K-BG121.

## USB service endpoints

| Service | OUT | IN | Image 0 | Images 1-3 |
| --- | --- | --- | --- | --- |
| BOOT | EP1 (`0x01`) | EP1 (`0x81`) | enabled | enabled |
| FLASH | EP2 (`0x02`) | EP2 (`0x82`) | enabled | disabled |
| UART | EP3 (`0x03`) | EP3 (`0x83`) | disabled | enabled |

EP0 is reserved for USB enumeration and standard/class control requests.

The current code defines the shared protocol constants, endpoint policy, and
the final BOOT request/quiesce controller. USB packet handling, flash commands,
UART FIFOs, and the physical USB engine remain to be implemented.

EP1 OUT carries exactly one byte: target image `0` through `3`. EP1 IN returns
one status byte (`0` accepted, `1` invalid image, `2` invalid manifest, or `3`
busy). The accepted response must finish before `BootController.request_valid`
is asserted; the controller then quiesces shared resources before warm boot.
