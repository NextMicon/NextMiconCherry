#!/usr/bin/env python3
"""Generate the placement-only NextMicon Grape PCB from its schematic."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pcbnew


HERE = Path(__file__).resolve().parent
PCB_DIR = HERE.parent
SRC_DIR = PCB_DIR / "src"
SCHEMATIC = SRC_DIR / "grape.kicad_sch"
BOARD = SRC_DIR / "grape.kicad_pcb"

BOARD_LEFT = 20.0
BOARD_TOP = 20.0
BOARD_RIGHT = 104.0
BOARD_BOTTOM = 84.0

GRAPE_STACKUP = """\
\t\t(stackup
\t\t\t(layer "F.SilkS"
\t\t\t\t(type "Top Silk Screen")
\t\t\t\t(color "White")
\t\t\t)
\t\t\t(layer "F.Paste"
\t\t\t\t(type "Top Solder Paste")
\t\t\t)
\t\t\t(layer "F.Mask"
\t\t\t\t(type "Top Solder Mask")
\t\t\t\t(color "Purple")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "F.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "dielectric 1"
\t\t\t\t(type "prepreg")
\t\t\t\t(thickness 0.2104)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.4)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "In1.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.0152)
\t\t\t)
\t\t\t(layer "dielectric 2"
\t\t\t\t(type "core")
\t\t\t\t(thickness 1.065)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.6)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "In2.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.0152)
\t\t\t)
\t\t\t(layer "dielectric 3"
\t\t\t\t(type "prepreg")
\t\t\t\t(thickness 0.2104)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.4)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "B.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "B.Mask"
\t\t\t\t(type "Bottom Solder Mask")
\t\t\t\t(color "Purple")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "B.Paste"
\t\t\t\t(type "Bottom Solder Paste")
\t\t\t)
\t\t\t(layer "B.SilkS"
\t\t\t\t(type "Bottom Silk Screen")
\t\t\t\t(color "White")
\t\t\t)
\t\t\t(copper_finish "HASL with lead")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def at(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def add_grid(
    placements: dict[str, tuple[float, float, float, str]],
    refs: list[str],
    xs: list[float],
    ys: list[float],
    *,
    angle: float = 0.0,
    side: str = "F",
) -> None:
    positions = [(x, y) for y in ys for x in xs]
    if len(refs) > len(positions):
        raise ValueError("placement grid is too small")
    for ref, (x, y) in zip(refs, positions, strict=False):
        placements[ref] = (x, y, angle, side)


def component_placements() -> dict[str, tuple[float, float, float, str]]:
    """Return x, y, angle and side for every schematic footprint."""

    p: dict[str, tuple[float, float, float, str]] = {
        # Board interfaces and the FPGA.
        # The USB4085 footprint marks its board edge 6.1 mm behind its origin.
        "J1": (62.0, 26.1, 180.0, "F"),
        "J2": (24.0, 28.0, 0.0, "F"),
        "J3": (98.5, 28.0, 0.0, "F"),
        "J4": (89.0, 80.0, 90.0, "F"),
        "U1": (62.0, 52.0, 0.0, "F"),
        # USB power entry and data protection.
        "F1": (49.0, 25.0, 0.0, "F"),
        "U7": (50.0, 30.0, 0.0, "F"),
        "U6": (68.5, 27.5, 0.0, "F"),
        # Three sequenced regulators, left to right from switcher to output.
        "U2": (34.5, 35.0, 0.0, "F"),
        "U3": (34.5, 43.0, 0.0, "F"),
        "U4": (34.5, 51.0, 0.0, "F"),
        "L1": (39.0, 35.0, 0.0, "F"),
        "L2": (39.0, 43.0, 0.0, "F"),
        "L3": (39.0, 51.0, 0.0, "F"),
        # Analog supply filter.
        "FB1": (44.5, 61.0, 0.0, "F"),
        "FB2": (44.5, 64.0, 0.0, "F"),
        # Clock and configuration flash.
        "X1": (78.0, 38.0, 0.0, "F"),
        "U5": (82.5, 52.5, 0.0, "F"),
        "JP1": (88.0, 61.5, 0.0, "F"),
        # User controls.
        "SW1": (34.0, 77.0, 0.0, "F"),
        "SW2": (44.0, 78.5, 0.0, "F"),
        "SW3": (81.0, 70.5, 0.0, "F"),
        "Q1": (56.5, 69.0, 0.0, "F"),
        # USB and power-entry capacitors.
        "C1": (54.0, 31.0, 0.0, "F"),
        "C2": (54.0, 34.0, 0.0, "F"),
        "C3": (30.5, 34.5, 90.0, "F"),
        "C4": (43.0, 29.5, 0.0, "F"),
        "C5": (30.5, 42.5, 90.0, "F"),
        "C6": (42.5, 34.0, 0.0, "F"),
        "C7": (46.0, 34.0, 0.0, "F"),
        "C8": (30.5, 50.5, 90.0, "F"),
        "C9": (42.5, 42.0, 0.0, "F"),
        "C10": (46.0, 42.0, 0.0, "F"),
        "C11": (30.5, 54.5, 90.0, "F"),
        "C12": (42.5, 50.0, 0.0, "F"),
        "C13": (46.0, 50.0, 0.0, "F"),
        "C14": (76.0, 26.0, 0.0, "F"),
        "C15": (61.0, 30.0, 0.0, "F"),
        "C16": (76.0, 34.5, 0.0, "F"),
        "C17": (79.0, 34.5, 0.0, "F"),
        # Analog rail parts.
        "C18": (47.5, 61.0, 0.0, "F"),
        "C19": (47.5, 63.0, 0.0, "F"),
        "C20": (47.5, 66.0, 0.0, "F"),
        # FPGA bulk and medium-frequency decoupling.
        "C21": (50.0, 53.5, 90.0, "F"),
        "C22": (50.0, 58.0, 90.0, "B"),
        "C23": (55.0, 40.0, 0.0, "F"),
        "C24": (58.0, 40.0, 0.0, "F"),
        "C29": (39.5, 61.0, 0.0, "F"),
        "C30": (61.5, 40.0, 0.0, "F"),
        "C31": (64.5, 40.0, 0.0, "F"),
        "C35": (68.5, 40.0, 0.0, "F"),
        "C36": (73.2, 39.0, 0.0, "F"),
        "C37": (75.0, 44.0, 90.0, "F"),
        "C38": (91.5, 57.5, 90.0, "F"),
        "C39": (70.5, 64.0, 0.0, "F"),
        "C40": (54.0, 64.0, 0.0, "F"),
        "C41": (57.0, 64.0, 0.0, "F"),
        "C42": (60.0, 64.0, 0.0, "F"),
        "C43": (63.0, 64.0, 0.0, "F"),
        "C44": (50.0, 40.0, 0.0, "F"),
        "C45": (70.0, 67.5, 0.0, "F"),
        "C46": (66.0, 67.5, 0.0, "F"),
        "C47": (51.5, 66.0, 90.0, "F"),
        # Power sequencing and feedback.
        "R1": (39.5, 29.5, 0.0, "F"),
        "R2": (34.0, 38.0, 0.0, "F"),
        "R3": (37.0, 38.0, 0.0, "F"),
        "R4": (40.0, 40.0, 0.0, "F"),
        "R5": (34.0, 46.0, 0.0, "F"),
        "R6": (37.0, 46.0, 0.0, "F"),
        "R7": (40.0, 48.0, 0.0, "F"),
        "R8": (34.0, 54.0, 0.0, "F"),
        "R9": (37.0, 54.0, 0.0, "F"),
        "R10": (40.0, 56.0, 0.0, "F"),
        "R11": (50.0, 33.5, 0.0, "F"),
        # USB data, CC and sensing.
        "R20": (70.5, 31.0, 0.0, "F"),
        "R21": (70.5, 33.5, 0.0, "F"),
        "R22": (67.5, 31.5, 90.0, "F"),
        "R23": (64.0, 31.5, 0.0, "F"),
        "R24": (64.0, 34.0, 0.0, "F"),
        "R25": (57.5, 32.5, 0.0, "F"),
        "R26": (60.0, 32.5, 0.0, "F"),
        "R27": (77.5, 29.5, 0.0, "F"),
        # QSPI series row and flash pull resistors.
        "R40": (76.5, 48.0, 0.0, "F"),
        "R41": (76.5, 50.5, 0.0, "F"),
        "R42": (76.5, 53.0, 0.0, "F"),
        "R43": (76.5, 55.5, 0.0, "F"),
        "R44": (76.5, 58.0, 0.0, "F"),
        "R45": (76.5, 60.5, 0.0, "F"),
        "R46": (91.0, 47.5, 0.0, "F"),
        "R47": (91.0, 50.0, 0.0, "F"),
        "R48": (91.0, 52.5, 0.0, "F"),
        # FPGA configuration straps and status controls.
        "R49": (79.0, 62.5, 0.0, "F"),
        "R50": (82.0, 62.5, 0.0, "F"),
        "R51": (85.0, 62.5, 0.0, "F"),
        "R52": (88.0, 68.5, 0.0, "F"),
        "R53": (76.0, 66.0, 0.0, "F"),
        "R54": (79.0, 66.0, 0.0, "F"),
        "R55": (82.0, 66.0, 0.0, "F"),
        "R56": (58.0, 72.5, 0.0, "F"),
        "R57": (73.5, 68.5, 0.0, "F"),
        "R58": (46.0, 68.5, 0.0, "F"),
        "R59": (49.0, 68.5, 0.0, "F"),
        "R60": (31.0, 72.5, 0.0, "F"),
        "R61": (34.0, 72.5, 0.0, "F"),
        # LED current limiting resistors.
        "R71": (52.0, 73.0, 0.0, "F"),
        "R73": (63.0, 73.0, 0.0, "F"),
        "R74": (68.0, 73.0, 0.0, "F"),
        "R75": (73.0, 73.0, 0.0, "F"),
        # PWR, CFG, PROG, USER0 and USER1 LEDs.
        "D1": (52.0, 77.0, 0.0, "F"),
        "D2": (58.0, 77.0, 0.0, "F"),
        "D3": (63.0, 77.0, 0.0, "F"),
        "D4": (68.0, 77.0, 0.0, "F"),
        "D5": (73.0, 77.0, 0.0, "F"),
    }

    # The smallest BGA decouplers go on the back directly under the package.
    back_decoupling = [
        "C25",
        "C26",
        "C27",
        "C28",
        "C32",
        "C33",
        "C34",
        "C48",
        "C49",
        "C50",
        "C51",
        "C52",
        "C53",
        "C54",
        "C55",
        "C56",
        "C57",
        "C58",
        "C59",
        "C60",
        "C61",
        "C62",
        "C63",
    ]
    add_grid(
        p,
        back_decoupling,
        [56.0, 58.4, 60.8, 63.2, 65.6, 68.0],
        [46.0, 49.2, 52.4, 55.6],
        side="B",
    )
    return p


def export_netlist() -> ET.Element:
    with tempfile.NamedTemporaryFile(suffix=".xml") as netlist:
        subprocess.run(
            [
                "kicad-cli",
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadxml",
                "-o",
                netlist.name,
                str(SCHEMATIC),
            ],
            check=True,
        )
        return ET.parse(netlist.name).getroot()


def footprint_root() -> Path:
    configured = os.environ.get("KICAD10_FOOTPRINT_DIR")
    if configured:
        return Path(configured)
    return Path("/usr/share/kicad/footprints")


def load_footprint(footprint_id: str) -> pcbnew.FOOTPRINT:
    library, name = footprint_id.split(":", 1)
    library_path = footprint_root() / f"{library}.pretty"
    footprint = pcbnew.FootprintLoad(str(library_path), name)
    if footprint is None:
        raise FileNotFoundError(f"cannot load {footprint_id} from {library_path}")
    return footprint


def add_outline(board: pcbnew.BOARD) -> None:
    corners = [
        (BOARD_LEFT, BOARD_TOP),
        (BOARD_RIGHT, BOARD_TOP),
        (BOARD_RIGHT, BOARD_BOTTOM),
        (BOARD_LEFT, BOARD_BOTTOM),
    ]
    for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetStart(at(*start))
        edge.SetEnd(at(*end))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(pcbnew.FromMM(0.05))
        board.Add(edge)


def add_text(
    board: pcbnew.BOARD,
    text: str,
    x: float,
    y: float,
    *,
    size: float = 1.0,
    angle: float = 0.0,
) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetPosition(at(x, y))
    item.SetLayer(pcbnew.F_SilkS)
    item.SetTextSize(at(size, size))
    item.SetTextThickness(pcbnew.FromMM(max(0.15, size * 0.16)))
    item.SetTextAngleDegrees(angle)
    board.Add(item)


def add_silkscreen(board: pcbnew.BOARD) -> None:
    add_text(board, "NEXTMICON GRAPE", 34.0, 23.5, size=1.2)
    add_text(board, "GPIO 0-27", 24.5, 81.0, size=0.8)
    add_text(board, "GPIO 28-55", 98.5, 23.0, size=0.8)
    add_text(board, "USB", 58.5, 29.5, size=0.8)
    add_text(board, "POWER", 35.0, 58.0, size=0.9)
    add_text(board, "IMAGE", 34.0, 81.0, size=0.8)
    add_text(board, "RESET", 44.0, 82.0, size=0.8)
    add_text(board, "PWR  CFG  PROG  U0   U1", 62.5, 80.0, size=0.65)
    add_text(board, "PROGRAM", 81.0, 74.0, size=0.7)
    add_text(board, "JTAG", 87.5, 82.0, size=0.8)
    add_text(board, "PLACEMENT ONLY - UNROUTED", 80.5, 30.5, size=0.65)


def configure_reference(footprint: pcbnew.FOOTPRINT, visible: bool) -> None:
    reference = footprint.Reference()
    reference.SetVisible(visible)
    reference.SetTextSize(at(0.65, 0.65))
    reference.SetTextThickness(pcbnew.FromMM(0.12))
    reference.SetKeepUpright(True)
    footprint.Value().SetVisible(False)


def create_board(netlist: ET.Element) -> pcbnew.BOARD:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    board.GetAllNetClasses()["Default"].SetClearance(pcbnew.FromMM(0.15))
    design_settings = board.GetDesignSettings()
    design_settings.m_CopperEdgeClearance = pcbnew.FromMM(0.25)
    design_settings.m_MinSilkTextHeight = pcbnew.FromMM(0.6)
    design_settings.m_MinSilkTextThickness = pcbnew.FromMM(0.1)

    title = board.GetTitleBlock()
    title.SetTitle("NextMicon Grape FPGA Board")
    title.SetDate("2026-08-10")
    title.SetRevision("A-placement")
    title.SetCompany("NextMicon")
    title.SetComment(0, "84 mm x 64 mm; four-layer placement study")
    title.SetComment(1, "Placement only: routing, vias and copper zones intentionally omitted")

    placements = component_placements()
    components = netlist.find("components")
    if components is None:
        raise ValueError("netlist contains no components")

    schematic_refs = {component.attrib["ref"] for component in components}
    if schematic_refs != placements.keys():
        missing = sorted(schematic_refs - placements.keys())
        extra = sorted(placements.keys() - schematic_refs)
        raise ValueError(f"placement mismatch; missing={missing}, extra={extra}")

    footprints: dict[str, pcbnew.FOOTPRINT] = {}
    for component in components:
        ref = component.attrib["ref"]
        value = component.findtext("value") or ""
        footprint_id = component.findtext("footprint")
        timestamp = component.findtext("tstamps")
        if not footprint_id or not timestamp:
            raise ValueError(f"{ref} lacks a footprint or schematic UUID")

        footprint = load_footprint(footprint_id)
        footprint.SetFPIDAsString(footprint_id)
        footprint.SetReference(ref)
        footprint.SetValue(value)
        for field in component.findall("./fields/field"):
            field_name = field.attrib["name"]
            if footprint.HasField(field_name):
                footprint.GetField(field_name).SetText(field.text or "")
        footprint.SetPath(pcbnew.KIID_PATH(timestamp))
        footprint.SetSheetname("/")
        footprint.SetSheetfile(SCHEMATIC.name)
        board.Add(footprint)

        x, y, angle, side = placements[ref]
        footprint.SetPosition(at(x, y))
        if side == "B":
            footprint.SetLayerAndFlip(pcbnew.B_Cu)
        footprint.SetOrientationDegrees(angle)
        configure_reference(footprint, visible=side == "F")
        footprints[ref] = footprint

    nets_element = netlist.find("nets")
    if nets_element is None:
        raise ValueError("netlist contains no nets")

    missing_pads: list[str] = []
    for code, net_element in enumerate(nets_element, start=1):
        net_name = net_element.attrib["name"]
        net = pcbnew.NETINFO_ITEM(board, net_name, code)
        board.Add(net)
        for node in net_element:
            ref = node.attrib["ref"]
            pin = node.attrib["pin"]
            matching_pads = [pad for pad in footprints[ref].Pads() if pad.GetNumber() == pin]
            if not matching_pads:
                missing_pads.append(f"{ref}.{pin}")
                continue
            for pad in matching_pads:
                pad.SetNet(net)

    if missing_pads:
        raise ValueError(f"footprint pads not found: {', '.join(missing_pads)}")

    add_outline(board)
    add_silkscreen(board)
    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(False)
    return board


def add_grape_stackup(board_path: Path) -> None:
    text = board_path.read_text(encoding="utf-8")
    setup_marker = "\t(setup\n"
    if "\t\t(stackup\n" in text:
        raise ValueError("generated board already contains a stackup")
    if setup_marker not in text:
        raise ValueError("generated board contains no setup section")
    board_path.write_text(
        text.replace(setup_marker, setup_marker + GRAPE_STACKUP, 1),
        encoding="utf-8",
    )


def main() -> None:
    netlist = export_netlist()
    board = create_board(netlist)
    pcbnew.SaveBoard(str(BOARD), board)
    add_grape_stackup(BOARD)
    print(f"wrote {BOARD}")


if __name__ == "__main__":
    main()
