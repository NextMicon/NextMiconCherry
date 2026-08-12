import re, math, sys

text = open('/home/turing/NextMicon/fpga/boards/cherry/breakout/src/fixture.kicad_pcb').read()
items = []
for m in re.finditer(r'\(segment \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(width ([\d.]+)\) \(layer "([^"]+)"\) \(net (\d+)\)', text):
    x1, y1, x2, y2, w = map(float, m.group(1, 2, 3, 4, 5))
    items.append((m.group(6), int(m.group(7)), x1, y1, x2, y2, w/2, 'seg'))
for m in re.finditer(r'\(via \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+)\)', text):
    x, y, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
    nm = re.search(r'\(net (\d+)\)', text[m.end():m.end()+200])
    for lay in ('F.Cu', 'B.Cu'):
        items.append((lay, int(nm.group(1)), x, y, x, y, s/2, 'via'))
pos = 0
while True:
    i = text.find('(footprint "', pos)
    if i < 0:
        break
    nxt = text.find('(footprint "', i+10)
    blk = text[i:nxt if nxt > 0 else len(text)]
    pos = i+10
    at = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', blk)
    fx, fy = float(at.group(1)), float(at.group(2))
    for pm in re.finditer(r'\(pad "([^"]*)" (?:np_)?thru_hole \w+ \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+)', blk):
        seg = blk[pm.start():pm.start()+400]
        nm = re.search(r'\(net (\d+)', seg)
        net = int(nm.group(1)) if nm else -99
        px, py, s = fx+float(pm.group(2)), fy+float(pm.group(3)), float(pm.group(4))
        for lay in ('F.Cu', 'B.Cu'):
            items.append((lay, net, px, py, px, py, s/2, f'pad@{fx},{fy}'))

def segdist(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    def pseg(px, py, x1, y1, x2, y2):
        dx, dy = x2-x1, y2-y1
        L2 = dx*dx+dy*dy
        if L2 == 0:
            return math.hypot(px-x1, py-y1)
        t = max(0, min(1, ((px-x1)*dx+(py-y1)*dy)/L2))
        return math.hypot(px-(x1+t*dx), py-(y1+t*dy))
    def ccw(ax, ay, bx, by, cx, cy):
        return (cy-ay)*(bx-ax) > (by-ay)*(cx-ax)
    if (ccw(ax1, ay1, bx1, by1, bx2, by2) != ccw(ax2, ay2, bx1, by1, bx2, by2) and
            ccw(ax1, ay1, ax2, ay2, bx1, by1) != ccw(ax1, ay1, ax2, ay2, bx2, by2)):
        return 0.0
    return min(pseg(ax1, ay1, *b), pseg(ax2, ay2, *b), pseg(bx1, by1, *a), pseg(bx2, by2, *a))

CLR = 0.2
viol = []
for i in range(len(items)):
    li, ni, xi1, yi1, xi2, yi2, ri, di = items[i]
    for j in range(i+1, len(items)):
        lj, nj, xj1, yj1, xj2, yj2, rj, dj = items[j]
        if li != lj or ni == nj:
            continue
        if min(xi1, xi2)-ri-rj-CLR > max(xj1, xj2) or min(xj1, xj2)-ri-rj-CLR > max(xi1, xi2):
            continue
        if min(yi1, yi2)-ri-rj-CLR > max(yj1, yj2) or min(yj1, yj2)-ri-rj-CLR > max(yi1, yi2):
            continue
        d = segdist((xi1, yi1, xi2, yi2), (xj1, yj1, xj2, yj2)) - ri - rj
        if d < CLR - 1e-9:
            viol.append((round(d, 3), di, li, ni, (xi1, yi1, xi2, yi2), dj, nj, (xj1, yj1, xj2, yj2)))
viol.sort()
print('lint violations:', len(viol))
for v in viol[:int(sys.argv[1]) if len(sys.argv) > 1 else 30]:
    print(v)
