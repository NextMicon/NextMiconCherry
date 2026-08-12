#!/usr/bin/env python3
"""Generate the unrouted XC7A100T NextMicon Melon placement study."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pcbnew


HERE = Path(__file__).resolve().parent
FPGA_ROOT = HERE.parents[3]
GRAPE_HELPERS = FPGA_ROOT / "boards/grape/board/tools/generate_placement.py"
spec = importlib.util.spec_from_file_location("grape_placement_helpers", GRAPE_HELPERS)
gp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gp)

BOARD = HERE.parent / "src/melon.kicad_pcb"
gp.LEFT, gp.TOP, gp.RIGHT, gp.BOTTOM = 20.0, 20.0, 170.0, 140.0


def generate() -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(6)
    board.GetAllNetClasses()["Default"].SetClearance(pcbnew.FromMM(0.15))
    settings = board.GetDesignSettings()
    settings.m_CopperEdgeClearance = pcbnew.FromMM(0.25)
    settings.m_MinSilkTextHeight = pcbnew.FromMM(0.6)
    settings.m_MinSilkTextThickness = pcbnew.FromMM(0.1)
    title = board.GetTitleBlock()
    title.SetTitle("NextMicon Melon XC7A100T Placement Study")
    title.SetDate("2026-08-12")
    title.SetRevision("A-placement")
    title.SetCompany("NextMicon")
    title.SetComment(0, "150 mm x 120 mm, six layers, placement only")
    title.SetComment(1, "UNROUTED: no schematic nets or copper zones")
    gp.outline(board)

    header = "Connector_PinHeader_2.54mm:PinHeader_2x24_P2.54mm_Vertical"
    # Two headers per row, four rows. Connector numbering remains J2 through J9.
    header_positions = (
        (27.0, 25.0), (96.0, 25.0),
        (27.0, 32.62), (96.0, 32.62),
        (27.0, 127.38), (96.0, 127.38),
        (27.0, 135.0), (96.0, 135.0),
    )
    for offset, (x, y) in enumerate(header_positions):
        first = offset * 32 + 1
        gp.add_fp(board, f"J{offset + 2}", f"GPIO {first}-{first + 31}", header, x, y, 90)

    gp.add_fp(board, "U1", "XC7A100T-1FGG676C", "Package_BGA:Xilinx_FGG676", 100.0, 80.0)
    gp.add_fp(board, "U5", "W25Q256JV", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", 126.0, 79.0)
    gp.add_fp(board, "X1", "100MHz XO", "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm", 78.0, 72.0)

    gp.add_fp(board, "J1", "USB-C USB2 Device", "Connector_USB:USB_C_Receptacle_GCT_USB4085", 26.1, 80.0, 90)
    gp.add_fp(board, "U6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", 38.0, 81.0)
    gp.add_fp(board, "F1", "1.1A HOLD", "Fuse:Fuse_1206_3216Metric", 38.0, 70.0)
    gp.add_fp(board, "U7", "TPS22917DBV", "Package_TO_SOT_SMD:SOT-23-6", 44.0, 90.0)

    # Placement reservations for the three sequenced rails; final regulator parts are not frozen.
    for index, y in enumerate((63.0, 74.0, 85.0), start=2):
        gp.add_fp(board, f"U{index}", "REGULATOR TBD", "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.75x1.75mm", 58.0, y)
        gp.add_fp(board, f"L{index - 1}", "1uH TBD", "Inductor_SMD:L_1210_3225Metric", 65.0, y)
        gp.add_fp(board, f"CIN{index}", "22uF", "Capacitor_SMD:C_1210_3225Metric", 50.0, y)
        gp.add_fp(board, f"COUT{index}", "47uF", "Capacitor_SMD:C_1210_3225Metric", 72.0, y)

    gp.add_fp(board, "J10", "JTAG", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", 153.0, 63.0, 90)
    gp.add_fp(board, "SW1", "PROGRAM", "Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2", 155.0, 83.0)
    gp.add_fp(board, "SW2", "USER", "Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2", 155.0, 95.0)
    gp.add_fp(board, "JP1", "DEFAULT_USER", "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", 145.0, 105.0, side="B")
    for index, x in enumerate((124.0, 132.0, 140.0, 148.0), start=1):
        gp.add_fp(board, f"D{index}", "STATUS LED", "LED_SMD:LED_0603_1608Metric", x, 51.0)
        gp.add_fp(board, f"RLED{index}", "1k", "Resistor_SMD:R_0402_1005Metric", x, 56.0)

    # Dense back-side decoupling field below the 27 mm FPGA package.
    refs = [f"C{number}" for number in range(20, 84)]
    positions = [(86.0 + col * 4.0, 66.0 + row * 4.0) for row in range(8) for col in range(8)]
    for ref, (x, y) in zip(refs, positions, strict=True):
        gp.add_fp(board, ref, "0.47uF", "Capacitor_SMD:C_0402_1005Metric", x, y, side="B")

    for index, (x, y) in enumerate(((25.0, 47.0), (165.0, 47.0), (25.0, 113.0), (165.0, 113.0)), start=1):
        gp.add_fp(board, f"H{index}", "M3 MOUNT", "MountingHole:MountingHole_3.2mm_M3", x, y)

    gp.add_text(board, "NEXTMICON MELON", 95.0, 42.0, 1.5)
    gp.add_text(board, "XC7A100T-FGG676 / 256 GPIO", 95.0, 46.0, 0.9)
    gp.add_text(board, "USB", 29.0, 88.0, 0.8)
    gp.add_text(board, "POWER", 61.0, 97.0, 0.8)
    gp.add_text(board, "QSPI", 126.0, 89.0, 0.8)
    gp.add_text(board, "JTAG", 158.0, 56.0, 0.8)
    gp.add_text(board, "DEFAULT USER", 145.0, 110.0, 0.8, "B")
    gp.add_text(board, "PLACEMENT ONLY / UNROUTED", 95.0, 118.0, 0.8)
    return board


def main() -> None:
    board = generate()
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"wrote {BOARD}")


if __name__ == "__main__":
    main()
