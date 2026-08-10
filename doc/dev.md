# Development guide

KiCad Version = 10.0.3

```
cherry/
├── doc/   # Documents
├── lib/   # Custom Footprints
├── src/   # KiCad Projects
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
$ kicad src/cherry.kicad_pro
```

## 4. Render board image

```bash
$ kicad-cli pcb render -o doc/img/cherry.png \
    --side top --width 1440 --height 720 --zoom 1.8 --quality high \
    src/cherry.kicad_pcb
```
