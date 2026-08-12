from __future__ import annotations

# ---------------- geometry constants (fixture frame, mm) ----------------
def XJ2(k): return round(36.37 + 2.54*(k-1), 2)
def XJ3(k): return round(94.79 - 2.54*(k-1), 2)
Y_J2_IN, Y_J2_OUT = 56.01, 58.55
Y_J3_IN, Y_J3_OUT = 33.15, 30.61
X_PJ4, X_J5, X_J6 = 94.79, 99.87, 10.0
def YJ4(j): return round(50.93 - 2.54*(j-1), 2)   # J4/J5/J6 pin rows (pin1 bottom for J4/J5)
def YJ6(j): return round(38.23 + 2.54*(j-1), 2)   # J6 pin1 top

# Pmod sockets: bottom rear/front rows, top rear/front rows
YB_REAR, YB_FRONT, YB_JOG = 77.0, 79.54, 78.27
YT_REAR, YT_FRONT, YT_JOG = 13.0, 10.46, 11.73
PMOD_CX = {'PMOD1': 27.48, 'PMOD2': 52.88, 'PMOD3': 78.28, 'PMOD4': 103.68,
           'PMOD8': 27.48, 'PMOD7': 52.88, 'PMOD6': 78.28, 'PMOD5': 103.68}
PMOD_EDGE = {'PMOD1':'B','PMOD2':'B','PMOD3':'B','PMOD4':'B',
             'PMOD5':'T','PMOD6':'T','PMOD7':'T','PMOD8':'T'}
def pmod_cols(name):
    cx = PMOD_CX[name]
    cols = [round(cx + off,2) for off in (-6.35,-3.81,-1.27,1.27,3.81,6.35)]
    if PMOD_EDGE[name] == 'T':
        cols = cols[::-1]          # top sockets rotated 180deg: pin1 at +x end
    return cols

# signal tables
J2_IN  = ['+5V','+3V3','CRESET_B','GND','GPIO1','GPIO2','GPIO3','GPIO4','GND','GPIO9','GPIO10','GPIO11','GPIO12','GND','GPIO17','GPIO18','GPIO19','GPIO20','GND','GPIO25','GPIO26','GPIO27','GPIO28','GND']
J2_OUT = ['+5V','+3V3','+3V3','+3V3','GPIO5','GPIO6','GPIO7','GPIO8','+3V3','GPIO13','GPIO14','GPIO15','GPIO16','+3V3','GPIO21','GPIO22','GPIO23','GPIO24','+3V3','GPIO29','GPIO30','GPIO31','GPIO32','+3V3']
J3_IN  = ['GND','GPIO33','GPIO34','GPIO35','GPIO36','GND','GPIO41','GPIO42','GPIO43','GPIO44','GND','GPIO49','GPIO50','GPIO51','GPIO52','GND','GPIO57','GPIO58','GPIO59','GPIO60','GND','GND','+3V3','+5V']
J3_OUT = ['+3V3','GPIO37','GPIO38','GPIO39','GPIO40','+3V3','GPIO45','GPIO46','GPIO47','GPIO48','+3V3','GPIO53','GPIO54','GPIO55','GPIO56','+3V3','GPIO61','GPIO62','GPIO63','GPIO64','+3V3','+3V3','+3V3','+5V']
J4SIG  = ['GND','CRESET_B','QSPI_CS_B','QSPI_SCK','QSPI_MOSI','QSPI_MISO']
J6SIG  = ['+5V','+3V3','GND','GND','CRESET_B','GND']   # J6 pin1..6 top->bottom

def gsrc(n):
    """source pogo (x, y) for GPIO n (opposed-block layout)"""
    if   1  <= n <= 4:  return XJ2(4+n),  Y_J2_IN
    elif 5  <= n <= 8:  return XJ2(n),    Y_J2_OUT
    elif 9  <= n <= 12: return XJ2(n+1),  Y_J2_IN
    elif 13 <= n <= 16: return XJ2(n-3),  Y_J2_OUT
    elif 17 <= n <= 20: return XJ2(n-2),  Y_J2_IN
    elif 21 <= n <= 24: return XJ2(n-6),  Y_J2_OUT
    elif 25 <= n <= 28: return XJ2(n-5),  Y_J2_IN
    elif 29 <= n <= 32: return XJ2(n-9),  Y_J2_OUT
    elif 33 <= n <= 36: return XJ3(n-31), Y_J3_IN
    elif 37 <= n <= 40: return XJ3(n-35), Y_J3_OUT
    elif 41 <= n <= 44: return XJ3(n-34), Y_J3_IN
    elif 45 <= n <= 48: return XJ3(n-38), Y_J3_OUT
    elif 49 <= n <= 52: return XJ3(n-37), Y_J3_IN
    elif 53 <= n <= 56: return XJ3(n-41), Y_J3_OUT
    elif 57 <= n <= 60: return XJ3(n-40), Y_J3_IN
    else:               return XJ3(n-44), Y_J3_OUT

PMOD_GPIO = {'PMOD1': list(range(1,9)),  'PMOD2': list(range(9,17)),
             'PMOD3': list(range(17,25)),'PMOD4': list(range(25,33)),
             'PMOD5': list(range(33,41)),'PMOD6': list(range(41,49)),
             'PMOD7': list(range(49,57)),'PMOD8': list(range(57,65))}

netnames = ['GND','+5V','+3V3','CRESET_B','QSPI_CS_B','QSPI_SCK','QSPI_MOSI','QSPI_MISO'] + [f'GPIO{i}' for i in range(1,65)]
netno = {n:i+1 for i,n in enumerate(netnames)}

_uid = [0]
def uid():
    _uid[0] += 1
    return f'00000000-0000-4000-8000-{_uid[0]:012d}'

def f2(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return s if s else '0'

out, tracks = [], []

def socket(ref, x0, y0, pads, body):
    """female socket; pads = list of (num, wx, wy, net); body = (x1,y1,x2,y2) silk rect"""
    parts = [f'(footprint "Fixture:Socket_{ref}" (layer "F.Cu") (at {f2(x0)} {f2(y0)}) (uuid "{uid()}") ']
    parts.append(f'(property "Reference" "{ref}" (at 0 -2.2) (layer "F.SilkS") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness .15)))) ')
    parts.append(f'(fp_rect (start {f2(body[0]-x0)} {f2(body[1]-y0)}) (end {f2(body[2]-x0)} {f2(body[3]-y0)}) (stroke (width .15) (type solid)) (fill none) (layer "F.SilkS") (uuid "{uid()}")) ')
    for num, wx, wy, net in pads:
        dx, dy = round(wx-x0,2), round(wy-y0,2)
        shape = 'rect' if num == 1 else 'circle'
        parts.append(f'(pad "{num}" thru_hole {shape} (at {f2(dx)} {f2(dy)}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {netno[net]} "{net}") (pinfunction "{net}") (pintype "passive") (uuid "{uid()}")) ')
    out.append(''.join(parts).rstrip() + ')')

def header(ref, x0, y0, pads, label_off=(2.5,2.5)):
    parts = [f'(footprint "Fixture:Header_1x{len(pads)}" (layer "F.Cu") (at {f2(x0)} {f2(y0)}) (uuid "{uid()}") ']
    parts.append(f'(property "Reference" "{ref}" (at {f2(label_off[0])} {f2(label_off[1])}) (layer "F.SilkS") (uuid "{uid()}") (effects (font (size 1 1) (thickness .15)))) ')
    pl = []; dxs = []
    for i,(wx,wy,net) in enumerate(pads):
        dx, dy = round(wx-x0,2), round(wy-y0,2)
        dxs.append((dx,dy))
        shape = 'rect' if i==0 else 'circle'
        pl.append(f'(pad "{i+1}" thru_hole {shape} (at {f2(dx)} {f2(dy)}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {netno[net]} "{net}") (pinfunction "{net}") (pintype "passive") (uuid "{uid()}")) ')
    xs=[d[0] for d in dxs]; ys=[d[1] for d in dxs]
    parts.append(f'(fp_rect (start {f2(min(xs)-1.4)} {f2(min(ys)-1.2)}) (end {f2(max(xs)+1.4)} {f2(max(ys)+1.2)}) (stroke (width .15) (type solid)) (fill none) (layer "F.SilkS") (uuid "{uid()}")) ')
    parts += pl
    out.append(''.join(parts).rstrip() + ')')

def pmod(ref):
    cols = pmod_cols(ref)
    edge = PMOD_EDGE[ref]
    y_rear  = YB_REAR if edge=='B' else YT_REAR
    y_front = YB_FRONT if edge=='B' else YT_FRONT
    g = PMOD_GPIO[ref]
    sig = {1:f'GPIO{g[0]}',2:f'GPIO{g[1]}',3:f'GPIO{g[2]}',4:f'GPIO{g[3]}',5:'GND',6:'+3V3',
           7:f'GPIO{g[4]}',8:f'GPIO{g[5]}',9:f'GPIO{g[6]}',10:f'GPIO{g[7]}',11:'GND',12:'+3V3'}
    x0 = PMOD_CX[ref]
    parts = [f'(footprint "Fixture:Pmod_2x6" (layer "F.Cu") (at {f2(x0)} {f2(y_rear)}) (uuid "{uid()}") ']
    lbl_y = 3.8 if edge=='B' else -3.8
    parts.append(f'(property "Reference" "{ref}" (at 0 {f2(lbl_y)}) (layer "F.SilkS") (hide yes) (uuid "{uid()}") (effects (font (size 1 1) (thickness .15)))) ')
    for p in range(1,13):
        col = cols[(p-1)%6]
        wy = y_rear if p<=6 else y_front
        dx, dy = round(col-x0,2), round(wy-y_rear,2)
        net = sig[p]
        shape = 'rect' if p==1 else 'circle'
        parts.append(f'(pad "{p}" thru_hole {shape} (at {f2(dx)} {f2(dy)}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {netno[net]} "{net}") (pinfunction "{net}") (pintype "passive") (uuid "{uid()}")) ')
    ymin = min(0, y_front-y_rear)-1.2; ymax = max(0, y_front-y_rear)+1.2
    parts.append(f'(fp_rect (start {f2(min(c-x0 for c in cols)-1.4)} {f2(ymin)}) (end {f2(max(c-x0 for c in cols)+1.4)} {f2(ymax)}) (stroke (width .15) (type solid)) (fill none) (layer "F.SilkS") (uuid "{uid()}")) ')
    out.append(''.join(parts).rstrip() + ')')

def vseg(x, y1, y2, net):
    tracks.append(f'(segment (start {f2(x)} {f2(y1)}) (end {f2(x)} {f2(y2)}) (width 0.25) (layer "B.Cu") (net {netno[net]}) (uuid "{uid()}"))')

def hseg(y, x1, x2, net, layer="F.Cu"):
    tracks.append(f'(segment (start {f2(x1)} {f2(y)}) (end {f2(x2)} {f2(y)}) (width 0.25) (layer "{layer}") (net {netno[net]}) (uuid "{uid()}"))')

def via(x, y, net):
    tracks.append(f'(via (at {f2(x)} {f2(y)}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {netno[net]}) (uuid "{uid()}"))')

def pmod_drop(ref, pin_idx, lane_y, net):
    """from (via point on lane_y at pad column) to pmod pad; pin_idx 1..12"""
    cols = pmod_cols(ref)
    col = cols[(pin_idx-1)%6]
    edge = PMOD_EDGE[ref]
    if edge == 'B':
        y_rear, y_front, y_jog = YB_REAR, YB_FRONT, YB_JOG
    else:
        y_rear, y_front, y_jog = YT_REAR, YT_FRONT, YT_JOG
    if pin_idx <= 6:
        via(col, lane_y, net)
        vseg(col, lane_y, y_rear, net)
    else:
        xoff = round(col + 1.27, 2)
        via(xoff, lane_y, net)
        vseg(xoff, lane_y, y_jog, net)
        hseg(y_jog, xoff, col, net, layer="B.Cu")
        vseg(col, y_jog, y_front, net)

def pin_of(ref, i):
    """i = 0..7 (D0..D7) -> pmod pin number"""
    return i+1 if i < 4 else i+3

# ---------------- board skeleton ----------------
out.append('(kicad_pcb (version 20240108) (generator "pcbnew") (general (thickness 1.6))')
out.append('(paper "A4") (title_block (title "NextMicon Cherry Pmod breakout board") (date "2026-08-12") (rev "0.5") (company "Next Micon"))')
out.append('(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen") (44 "Edge.Cuts" user) (49 "F.Fab" user))')
out.append('(setup (pad_to_mask_clearance 0)) (net 0 "")' + ''.join(f' (net {netno[n]} "{n}")' for n in netnames))

# female sockets that the Cherry headers plug into (pin numbers = Cherry pad numbers)
s2 = []
s3 = []
for k in range(1,25):
    s2.append((2*k-1, XJ2(k), Y_J2_IN,  J2_IN[k-1]))
    s2.append((2*k,   XJ2(k), Y_J2_OUT, J2_OUT[k-1]))
    s3.append((2*k-1, XJ3(k), Y_J3_IN,  J3_IN[k-1]))
    s3.append((2*k,   XJ3(k), Y_J3_OUT, J3_OUT[k-1]))
socket('S2', XJ2(1), Y_J2_IN, s2, (XJ2(1)-1.9, Y_J2_IN-1.6, XJ2(24)+1.9, Y_J2_OUT+1.6))
socket('S3', XJ3(1), Y_J3_IN, s3, (XJ3(24)-1.9, Y_J3_OUT-1.6, XJ3(1)+1.9, Y_J3_IN+1.6))
socket('S4', X_PJ4, YJ4(1), [(j, X_PJ4, YJ4(j), J4SIG[j-1]) for j in range(1,7)],
       (X_PJ4-1.6, YJ4(6)-1.9, X_PJ4+1.6, YJ4(1)+1.9))

# connectors
header('J5', X_J5, YJ4(1), [(X_J5, YJ4(j), J4SIG[j-1]) for j in range(1,7)])
header('J6', X_J6, YJ6(1), [(X_J6, YJ6(j), J6SIG[j-1]) for j in range(1,7)], label_off=(2.5,-2.5))
for ref in ('PMOD1','PMOD2','PMOD3','PMOD4','PMOD5','PMOD6','PMOD7','PMOD8'):
    pmod(ref)

# ---------------- routing ----------------
# J5 SPI horizontals (B.Cu, pad row y)
for j in range(1,7):
    hseg(YJ4(j), X_PJ4, X_J5, J4SIG[j-1], layer="B.Cu")

# +5V spine: connects 4 pogos at x=36.37, plus branch to J6.1
vseg(36.37, Y_J3_OUT, 60.0, '+5V')
via(36.37, 60.0, '+5V')
hseg(60.0, 36.37, 7.0, '+5V')
via(7.0, 60.0, '+5V')
vseg(7.0, 60.0, YJ6(1), '+5V')
via(7.0, YJ6(1), '+5V')
hseg(YJ6(1), 7.0, X_J6, '+5V')

# CRESET_B: one straight F.Cu lane at y=48.39 from J6.5 to P_J4_2 pad, tapping P_J2_3
hseg(48.39, X_J6, X_PJ4, 'CRESET_B')
via(41.45, 48.39, 'CRESET_B')
vseg(41.45, 48.39, Y_J2_IN, 'CRESET_B')


# ---- direct escapes: D4-D7 (outer row) ----
def direct4(ref, lanes_deep_first):
    """gpios[4:8] straight to edge band; lanes_deep_first[0] = nearest board edge."""
    g = PMOD_GPIO[ref]
    for k, n in enumerate(g[4:8]):          # k=0 -> D4
        xs, sy = gsrc(n)
        lane = lanes_deep_first[k]          # D4 deepest (edge-most)
        net = f'GPIO{n}'
        pin = 7 + k
        vseg(xs, sy, lane, net)
        via(xs, lane, net)
        col = pmod_cols(ref)[(pin-1)%6]
        xoff = round(col + 1.27, 2)
        hseg(lane, xs, xoff, net)
        pmod_drop(ref, pin, lane, net)

# bottom bundles (larger y = deeper): A = PMOD1+PMOD3, B = PMOD2+PMOD4
BOT_A = [62.95, 62.3, 61.65, 61.0]
BOT_B = [65.55, 64.9, 64.25, 63.6]
# top bundles (smaller y = deeper): A = PMOD5+PMOD7, B = PMOD6+PMOD8
TOP_A = [26.36, 27.04, 27.72, 28.4]
TOP_B = [23.64, 24.32, 25.0, 25.68]
direct4('PMOD1', BOT_A); direct4('PMOD3', BOT_A)
direct4('PMOD2', BOT_B); direct4('PMOD4', BOT_B)
direct4('PMOD5', TOP_A[::-1]); direct4('PMOD7', TOP_A[::-1])
direct4('PMOD6', TOP_B[::-1]); direct4('PMOD8', TOP_B[::-1])

# ---- west-around escapes: D0-D3 (inner rows) via left margin ----
def west4(ref, mids, margs, bands, idx=range(4)):
    g = PMOD_GPIO[ref]
    for k in idx:
        n = g[k]
        xs, sy = gsrc(n)
        net = f'GPIO{n}'
        mid, mx, bl = mids[k], margs[k], bands[k]
        vseg(xs, sy, mid, net)
        via(xs, mid, net)
        hseg(mid, xs, mx, net)
        via(mx, mid, net)
        vseg(mx, mid, bl, net)
        via(mx, bl, net)
        col = pmod_cols(ref)[k]             # pins 1-4
        hseg(bl, mx, col, net)
        pmod_drop(ref, k+1, bl, net)

MID_P1 = [44.0, 44.65, 45.3, 45.95]
MID_P2 = [46.6, 47.25, 49.05, 49.7]         # gap at 48.39 for CRESET
MID_P3 = [50.35, 51.0, 51.65, 52.3]
MID_P4W = [43.35]                            # PMOD4 D0 goes west too
MID_P6 = [35.0, 35.65, 36.3, 36.95]
MID_P7 = [37.6, 38.25, 38.9, 39.55]
MID_P8 = [40.2, 40.85, 41.5, 42.15]
MG_A = [13.0, 13.65, 14.3, 14.95]
MG_B = [15.6, 16.25, 16.9, 17.55]
MG_C = [18.2, 18.85, 19.5, 20.15]
MG_D = [12.35]
BND_P1 = [66.2, 66.85, 67.5, 68.15]
BND_P2 = [68.8, 69.45, 70.1, 70.75]
BND_P3 = [71.4, 72.05, 72.7, 73.35]
BND_P4W = [74.0]
BND_P8 = [22.96, 22.31, 21.66, 21.01]
BND_P7 = [20.36, 19.71, 19.06, 18.41]
BND_P6 = [17.76, 17.11, 16.46, 15.81]

west4('PMOD1', MID_P1, MG_A, BND_P1)
west4('PMOD2', MID_P2, MG_B, BND_P2)
west4('PMOD3', MID_P3, MG_C, BND_P3)
west4('PMOD8', MID_P8, MG_A, BND_P8)
west4('PMOD7', MID_P7, MG_B, BND_P7)
west4('PMOD6', MID_P6, MG_C, BND_P6)
# PMOD4 D0 west-around (its own lanes)
west4('PMOD4', MID_P4W*4, MG_D*4, BND_P4W*4, idx=[0])

# ---- east escapes via corridors + right margin ----
SC_LANES = [52.55, 53.2, 53.85]              # PMOD4 D1-D3 southbound
NC_LANES = [34.6, 35.25, 35.9, 36.55]        # PMOD5 D0-D3 northbound
EV_X     = [113.45, 114.1, 114.75, 115.4]
BND_P4E  = [66.85, 67.5, 68.15]              # x-disjoint from PMOD1 usage
BND_P5   = [22.96, 22.31, 21.66, 21.01]      # x-disjoint from PMOD8 usage

g4 = PMOD_GPIO['PMOD4']
for k in (1, 2, 3):                          # D1-D3
    n = g4[k]
    xs, sy = gsrc(n)
    net = f'GPIO{n}'
    lane, ev, bl = SC_LANES[k-1], EV_X[k], BND_P4E[k-1]
    vseg(xs, sy, lane, net)
    via(xs, lane, net)
    hseg(lane, xs, ev, net)
    via(ev, lane, net)
    vseg(ev, lane, bl, net)
    via(ev, bl, net)
    col = pmod_cols('PMOD4')[k]
    hseg(bl, ev, col, net)
    pmod_drop('PMOD4', k+1, bl, net)

g5 = PMOD_GPIO['PMOD5']
for k in range(4):                           # D0-D3
    n = g5[k]
    xs, sy = gsrc(n)
    net = f'GPIO{n}'
    lane, ev, bl = NC_LANES[k], EV_X[k], BND_P5[k]
    vseg(xs, sy, lane, net)
    via(xs, lane, net)
    hseg(lane, xs, ev, net)
    via(ev, lane, net)
    vseg(ev, lane, bl, net)
    via(ev, bl, net)
    col = pmod_cols('PMOD5')[k]
    hseg(bl, ev, col, net)
    pmod_drop('PMOD5', k+1, bl, net)

# GND stitch: P_J3_6 pad sits in a B.Cu pocket fenced by tracks/pogo rows
vseg(82.09, 33.15, 40.0, 'GND')

# ---------------- zones ----------------
def zone(net, layer):
    return (f'(zone (net {netno[net]}) (net_name "{net}") (layer "{layer}") (uuid "{uid()}") (hatch edge 0.5) '
            f'(connect_pads (clearance 0.25)) (min_thickness 0.25) '
            f'(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.4)) '
            f'(polygon (pts (xy 5 5) (xy 125 5) (xy 125 85) (xy 5 85))))')
out_zones = [zone('GND','B.Cu'), zone('+3V3','F.Cu')]

# ---------------- graphics ----------------
gfx = []
gfx.append('(gr_rect (start 5 5) (end 125 85) (stroke (width .2) (type solid)) (fill none) (layer "Edge.Cuts") (uuid "%s"))' % uid())
gfx.append('(gr_rect (start 35 29) (end 96.16 60.16) (stroke (width .25) (type dash)) (fill none) (layer "F.Fab") (uuid "%s"))' % uid())
texts = [
 ('NEXTMICON CHERRY PMOD BREAKOUT', 65, 7.2, 1.2),
 ('PMOD8 57-64', 27.48, 16.2, 0.8), ('PMOD7 49-56', 52.88, 16.2, 0.8),
 ('PMOD6 41-48', 78.28, 16.2, 0.8), ('PMOD5 33-40', 103.68, 16.2, 0.8),
 ('PMOD1 1-8', 27.48, 74.7, 0.8), ('PMOD2 9-16', 52.88, 74.7, 0.8),
 ('PMOD3 17-24', 78.28, 74.7, 0.8), ('PMOD4 25-32', 103.68, 74.7, 0.8),
 ('J5 SPI', 108, 44.5, 0.8), ('J6 PWR/CRESET', 17, 34.5, 0.8),
 ('USB-C SIDE', 25, 62, 0.9),
]
for t,x,y,s in texts:
    gfx.append(f'(gr_text "{t}" (at {f2(x)} {f2(y)}) (layer "F.SilkS") (uuid "{uid()}") (effects (font (size {s} {s}) (thickness .13))))')
for x,y in ((10,10),(120,10),(10,80),(120,80)):
    gfx.append(f'(footprint "Fixture:MountingHole_M3" (layer "F.Cu") (at {x} {y}) (uuid "{uid()}") (pad "" np_thru_hole circle (at 0 0) (size 3.4 3.4) (drill 3.4) (layers "*.Cu" "*.Mask") (uuid "{uid()}")))')

body = out + gfx + tracks + out_zones + [')']
open('/home/turing/NextMicon/fpga/boards/cherry/breakout/src/fixture.kicad_pcb','w').write('\n'.join(body)+'\n')
print('items:', len(body), 'tracks+vias:', len(tracks))
