cherry.png: board/src/cherry.kicad_pcb
	kicad-cli pcb render -o $@ --side top --width 1440 --height 720 --zoom 1.8 --quality high $^

board/schematic.pdf: board/src/cherry.kicad_sch
	kicad-cli sch export pdf -o $@ $^

board/board.pdf: board/src/cherry.kicad_pcb
	kicad-cli pcb export pdf -o $@ --mode-multipage --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,F.Paste,B.Paste --common-layers Edge.Cuts $^
