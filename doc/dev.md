# Development guide

KiCad Version = 10.0.3

```
boards/cherry/
├── board/      # KiCad project, libraries, and fabrication outputs
├── breakout/   # Breakout and factory-test fixture
├── firmware/   # FPGA HDL and constraints
└── README.md
```

## 1. Install KiCad

```bash
$ sudo add-apt-repository --yes ppa:kicad/kicad-10.0-releases
$ sudo apt update
$ sudo apt install --install-recommends kicad
$ kicad-cli version
10.0.3
```

## 2. Setup KiCad MCP

TBD

## 3. Open KiCad project

```
$ kicad boards/cherry/board/src/cherry.kicad_pro
```

## 4. Render board image

```bash
$ kicad-cli pcb render -o boards/cherry/cherry.png \
    --side top --width 1440 --height 720 --zoom 1.8 --quality high \
    boards/cherry/board/src/cherry.kicad_pcb
```
