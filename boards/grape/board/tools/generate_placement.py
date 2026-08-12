#!/usr/bin/env python3
"""Generate the unrouted XC7S50 NextMicon Grape placement study."""

from __future__ import annotations

from pathlib import Path

import pcbnew


HERE = Path(__file__).resolve().parent
BOARD = HERE.parent / "src/grape.kicad_pcb"
FP_ROOT = Path("/usr/share/kicad/footprints")
LEFT, TOP, RIGHT, BOTTOM = 20.0, 20.0, 160.0, 90.0


def mm(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def load(fpid: str) -> pcbnew.FOOTPRINT:
    library, name = fpid.split(":", 1)
    footprint = pcbnew.FootprintLoad(str(FP_ROOT / f"{library}.pretty"), name)
    if footprint is None:
        raise FileNotFoundError(fpid)
    footprint.SetFPIDAsString(fpid)
    return footprint


def add_fp(
    board: pcbnew.BOARD,
    ref: str,
    value: str,
    fpid: str,
    x: float,
    y: float,
    angle: float = 0.0,
    side: str = "F",
) -> pcbnew.FOOTPRINT:
    footprint = load(fpid)
    footprint.SetReference(ref)
    footprint.SetValue(value)
    board.Add(footprint)
    footprint.SetPosition(mm(x, y))
    if side == "B":
        footprint.SetLayerAndFlip(pcbnew.B_Cu)
    footprint.SetOrientationDegrees(angle)
    footprint.Reference().SetVisible(True)
    footprint.Reference().SetTextSize(mm(0.7, 0.7))
    footprint.Reference().SetTextThickness(pcbnew.FromMM(0.12))
    footprint.Value().SetVisible(False)
    return footprint


def add_text(board: pcbnew.BOARD, value: str, x: float, y: float, size: float = 1.0, side: str = "F") -> None:
    text = pcbnew.PCB_TEXT(board)
    text.SetText(value)
    text.SetPosition(mm(x, y))
    text.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
    if side == "B":
        text.SetMirrored(True)
    text.SetTextSize(mm(size, size))
    text.SetTextThickness(pcbnew.FromMM(max(0.12, size * 0.16)))
    board.Add(text)


def outline(board: pcbnew.BOARD) -> None:
    points = [(LEFT, TOP), (RIGHT, TOP), (RIGHT, BOTTOM), (LEFT, BOTTOM)]
    for start, end in zip(points, points[1:] + points[:1], strict=True):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetStart(mm(*start))
        edge.SetEnd(mm(*end))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(pcbnew.FromMM(0.05))
        board.Add(edge)


def generate() -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    board.GetAllNetClasses()["Default"].SetClearance(pcbnew.FromMM(0.15))
    settings = board.GetDesignSettings()
    settings.m_CopperEdgeClearance = pcbnew.FromMM(0.25)
    settings.m_MinSilkTextHeight = pcbnew.FromMM(0.6)
    settings.m_MinSilkTextThickness = pcbnew.FromMM(0.1)
    title = board.GetTitleBlock()
    title.SetTitle("NextMicon Grape XC7S50 Placement Study")
    title.SetDate("2026-08-12")
    title.SetRevision("B-placement")
    title.SetCompany("NextMicon")
    title.SetComment(0, "140 mm x 70 mm, four layers, placement only")
    title.SetComment(1, "UNROUTED: no schematic nets or copper zones")
    outline(board)

    # Four Cherry-style 2x24 GPIO headers. Pin 1 is at the marked end.
    header = "Connector_PinHeader_2.54mm:PinHeader_2x24_P2.54mm_Vertical"
    add_fp(board, "J2", "GPIO 1-32", header, 27.0, 25.0, 90)
    add_fp(board, "J3", "GPIO 33-64", header, 96.0, 25.0, 90)
    add_fp(board, "J4", "GPIO 65-96", header, 27.0, 85.0, 90)
    add_fp(board, "J5", "GPIO 97-128", header, 96.0, 85.0, 90)

    # FPGA and parts that must remain physically close to it.
    add_fp(board, "U1", "XC7S50-1CSGA324C", "Package_BGA:Xilinx_CSGA324", 90.0, 55.0)
    add_fp(board, "U5", "W25Q128JVSIQ", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", 110.0, 54.0)
    add_fp(board, "X1", "100MHz XO", "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm", 76.0, 50.0)

    # USB is centered on the left edge; protection and entry power follow inward.
    add_fp(board, "J1", "USB-C USB2 Device", "Connector_USB:USB_C_Receptacle_GCT_USB4085", 26.1, 55.0, 90)
    add_fp(board, "U6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", 38.0, 56.0)
    add_fp(board, "F1", "1.1A HOLD", "Fuse:Fuse_1206_3216Metric", 38.0, 47.0)
    add_fp(board, "U7", "TPS22917DBV", "Package_TO_SOT_SMD:SOT-23-6", 43.0, 63.0)

    # Sequenced 1.0 V, 1.8 V and 3.3 V switchers form one compact power island.
    for index, y in enumerate((40.0, 47.0, 54.0), start=2):
        add_fp(board, f"U{index}", "TPS62A02DRL", "Package_TO_SOT_SMD:SOT-563", 47.0, y)
        add_fp(board, f"L{index - 1}", "1uH", "Inductor_SMD:L_0805_2012Metric", 52.0, y)
        add_fp(board, f"CIN{index}", "10uF", "Capacitor_SMD:C_0805_2012Metric", 43.0, y)
        add_fp(board, f"COUT{index}", "22uF", "Capacitor_SMD:C_0805_2012Metric", 56.0, y)

    # Configuration, debug and user controls on the right edge.
    add_fp(board, "J6", "JTAG", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", 143.0, 45.0, 90)
    add_fp(board, "SW1", "PROGRAM", "Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2", 145.0, 60.0)
    add_fp(board, "SW2", "USER", "Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2", 145.0, 70.0)
    add_fp(board, "JP1", "DEFAULT_USER", "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", 132.0, 72.0, side="B")

    for index, x in enumerate((120.0, 126.0, 132.0), start=1):
        add_fp(board, f"D{index}", "STATUS LED", "LED_SMD:LED_0603_1608Metric", x, 33.0)
        add_fp(board, f"RLED{index}", "1k", "Resistor_SMD:R_0402_1005Metric", x, 37.0)

    # BGA decouplers are placed on the back directly below the supply-ball field.
    refs = [f"C{number}" for number in range(20, 52)]
    positions = [(78.0 + col * 3.0, 43.0 + row * 3.0) for row in range(8) for col in range(4)]
    for ref, (x, y) in zip(refs, positions, strict=True):
        add_fp(board, ref, "0.47uF", "Capacitor_SMD:C_0402_1005Metric", x, y, side="B")

    add_text(board, "NEXTMICON GRAPE", 90.0, 29.5, 1.3)
    add_text(board, "XC7S50-CSGA324 / 128 GPIO", 90.0, 32.5, 0.8)
    add_text(board, "USB", 28.0, 61.5, 0.7)
    add_text(board, "POWER", 49.0, 59.0, 0.7)
    add_text(board, "QSPI", 110.0, 60.5, 0.7)
    add_text(board, "JTAG", 154.0, 37.0, 0.7)
    add_text(board, "DEFAULT USER", 132.0, 76.0, 0.7, "B")
    add_text(board, "PLACEMENT ONLY / UNROUTED", 90.0, 80.5, 0.7)
    return board


def main() -> None:
    board = generate()
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"wrote {BOARD}")


if __name__ == "__main__":
    main()
