#!/usr/bin/env python3
"""
Parametric CAD source for the 18650 Bluetooth speaker.

Generates every CAD file in the repo's cad/ folder:
    print/      01_enclosure_base, 02_enclosure_lid (.step + .stl, STLs in print orientation)
    reference/  03-09 purchased-part models (.step)
    assembly/   00_full_assembly, 00_layout_flat_all_parts (.step)

    pip install cadquery
    python speaker_cad.py            # run from cad/, writes into ./print, ./reference, ./assembly
    python speaker_cad.py out_dir    # writes the same folders under out_dir instead

Change a dimension in the PARAMETERS block and re-run. Optional environment variables:
    SPEAKER_NAME   text embossed on the front wall (default "Rishi"; keep it short, ~5-8 letters)
    SPEAKER_FONT   path to a .ttf font for that text (default: CadQuery's default font)

All dimensions are millimetres. Part models are simplified envelopes of purchased parts; where a
dimension is marked ASSUMED it was not published by the maker and should be checked against your part.
"""
import math
import os
import sys

import cadquery as cq

# =====================================================================================
# PARAMETERS
# =====================================================================================
NAME = os.environ.get("SPEAKER_NAME", "Rishi")
FONT_PATH = os.environ.get("SPEAKER_FONT")

# --- enclosure ---
WALL, FLOOR, LID_T = 2.5, 2.5, 3.0
IX, IY, IZ = 78.0, 46.0, 40.0          # interior size (X length, Y width, Z height)
CORNER_R = 3.0
BOSS_Y, BOSS_D = 21.2, 5.0             # corner screw boss (X position is derived below)
PILOT_D, PILOT_DEPTH = 1.8, 8.0        # M2 x 8 self-tapping screws
CLEAR_D, CBORE_D, CBORE_DEPTH = 2.4, 4.4, 1.2
TEXT_SIZE, TEXT_EMBOSS = 17, 0.8       # embossed name on the front (-Y) wall

# --- purchased parts (published dimensions unless marked) ---
# DFRobot DFR0720 / MH-M38 amp board: 45 x 20 mm outline published; height ASSUMED 5.0 mm
AMP_L, AMP_W, AMP_PCB_T, AMP_H = 45.0, 20.0, 1.6, 5.0
# TP4056 Type-C module (DW01A + 8205A), ~28 x 17 x 4 mm; USB-C shell is the standard 16-pin size
TP_L, TP_W, TP_PCB_T = 28.0, 17.0, 0.8
USB_C_L, USB_C_W, USB_C_H = 7.35, 8.94, 3.26
# 40 mm round driver (Adafruit 3968): 40 mm dia x 20 mm tall
DRV_D, DRV_H = 40.0, 20.0
# Samsung INR18650-25R, flat top, unprotected: max envelope 18.4 x 65.0 mm
CELL_D, CELL_L = 18.4, 65.0

# SS12D00G4 slide switch: body ~8.6 x 3.6 x 3.5 mm, 4 mm lever (check your part)
SW_L, SW_W, SW_H, SW_LEVER, SW_LEVER_L = 8.6, 3.6, 3.5, 1.5, 4.0
SW_CY, SW_CZ = 0.0, 30.0                # switch centre on the +X end wall
SW_POCKET_L, SW_POCKET_W = 9.0, 4.2     # recess on the inside of the wall for the body
SW_WALL_LEFT = 1.4                      # wall left behind the recess
SW_SLOT_L, SW_SLOT_W = 4.3, 2.1         # lever slot through the wall (lever 1.5 mm + 2 mm travel)

# --- placement inside the enclosure ---
CELL_CY = -13.0                         # cell axis Y position (cell lies along X)
TP_CY, AMP_CX, AMP_CY = 8.5, 13.4, 8.5
PLINTH_H = 3.0                          # board plinth height above the floor

# derived
OX, OY = IX + 2 * WALL, IY + 2 * WALL
Z_LID_IN = FLOOR + IZ                   # underside of the lid
Z_TOP = Z_LID_IN + LID_T
BOSS_X = IX / 2 - 0.8
CELL_AXIS_Z = FLOOR + 9.6
TP_CX = -IX / 2 + 0.3 + TP_L / 2        # USB-C end sits 0.3 mm off the -X wall
TP_Z = AMP_Z = FLOOR + PLINTH_H


# =====================================================================================
# PURCHASED-PART MODELS
# =====================================================================================
def amp_board():
    pcb = cq.Workplane("XY").box(AMP_L, AMP_W, AMP_PCB_T, centered=(True, True, False))
    env = cq.Workplane("XY").box(AMP_L - 3, AMP_W - 3, AMP_H - AMP_PCB_T, centered=(True, True, False)).translate((0, 0, AMP_PCB_T))
    return pcb.union(env)


def charger_module():
    pcb = cq.Workplane("XY").box(TP_L, TP_W, TP_PCB_T, centered=(True, True, False))
    usb = cq.Workplane("XY").box(USB_C_L, USB_C_W, USB_C_H, centered=(False, True, False)).translate((-TP_L / 2, 0, TP_PCB_T))
    chips = cq.Workplane("XY").box(18.0, 13.0, 1.5, centered=(False, True, False)).translate((-5.0, 0, TP_PCB_T))
    return pcb.union(usb).union(chips)


def driver():
    """Front face at z=0, body toward -Z."""
    body = cq.Workplane("XY").circle(DRV_D / 2).extrude(-DRV_H).faces("<Z").edges().chamfer(1.0)
    dish = (cq.Workplane("XZ").polyline([(0, 0.1), (17.0, 0.1), (17.0, 0), (6.0, -4.0), (0, -4.0)])
            .close().revolve(360, (0, 0, 0), (0, 1, 0)))
    return body.cut(dish)


def cell():
    """Axis along +Z."""
    c = cq.Workplane("XY").circle(CELL_D / 2).extrude(CELL_L)
    return c.faces("<Z").edges().chamfer(0.5).faces(">Z").edges().chamfer(0.5)


def screw():
    """M2 x 8 pan-head self-tapping screw, head down at z=0."""
    head = cq.Workplane("XY").circle(2.0).extrude(1.3)
    shank = cq.Workplane("XY").workplane(offset=1.3).circle(1.0).extrude(8.0)
    return head.union(shank)


def slide_switch():
    """SS12D00G4, lever pointing +X, body back face at x=0."""
    body = cq.Workplane("XY").box(SW_H, SW_L, SW_W, centered=(False, True, True))
    lever = cq.Workplane("XY").box(SW_LEVER_L, SW_LEVER, SW_LEVER, centered=(False, True, True)).translate((SW_H, 0, 0))
    sw = body.union(lever)
    for py in (-2.0, 0.0, 2.0):
        sw = sw.union(cq.Workplane("XY").box(3.0, 0.5, 0.5, centered=(False, True, True)).translate((-3.0, py, 0)))
    return sw


def nickel_tab():
    """0.15 x 8 mm pure nickel strip, 25 mm piece (length is arbitrary)."""
    return cq.Workplane("XY").box(25.0, 8.0, 0.15, centered=False)


# =====================================================================================
# ENCLOSURE
# =====================================================================================
def pocket(cx, cy, L, W, plinth_h, rim_h, skip=(), c=0.3, t=1.0):
    """Raised plinth with a perimeter rim that holds a PCB; `skip` lists sides left open."""
    z0 = FLOOR - 0.01
    p = cq.Workplane("XY").box(L + 2 * c, W + 2 * c, plinth_h + 0.01, centered=(True, True, False)).translate((cx, cy, z0))
    bars = {
        "+x": ((cx + L / 2 + c + t / 2, cy), (t, W + 2 * c + 2 * t)),
        "-x": ((cx - L / 2 - c - t / 2, cy), (t, W + 2 * c + 2 * t)),
        "+y": ((cx, cy + W / 2 + c + t / 2), (L + 2 * c + 2 * t, t)),
        "-y": ((cx, cy - W / 2 - c - t / 2), (L + 2 * c + 2 * t, t)),
    }
    for k, ((bx, by), (sx, sy)) in bars.items():
        if k not in skip:
            p = p.union(cq.Workplane("XY").box(sx, sy, plinth_h + rim_h + 0.01, centered=(True, True, False)).translate((bx, by, z0)))
    return p


def build_base():
    b = cq.Workplane("XY").box(OX, OY, Z_LID_IN, centered=(True, True, False)).edges("|Z").fillet(CORNER_R)
    b = b.cut(cq.Workplane("XY").box(IX, IY, IZ + 0.01, centered=(True, True, False)).translate((0, 0, FLOOR)))
    for sx in (-1, 1):                                             # corner screw bosses
        for sy in (-1, 1):
            b = b.union(cq.Workplane("XY").workplane(offset=FLOOR - 0.01).center(sx * BOSS_X, sy * BOSS_Y)
                        .circle(BOSS_D / 2).extrude(IZ + 0.01))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b = b.cut(cq.Workplane("XY").workplane(offset=Z_LID_IN - PILOT_DEPTH).center(sx * BOSS_X, sy * BOSS_Y)
                      .circle(PILOT_D / 2).extrude(PILOT_DEPTH + 0.01))
    b = b.union(pocket(TP_CX, TP_CY, TP_L, TP_W, PLINTH_H, 2.0, skip=("-x", "+x")))   # USB-C end open; divider belongs to amp pocket
    b = b.union(pocket(AMP_CX, AMP_CY, AMP_L, AMP_W, PLINTH_H, 2.5))
    for sx in (-1, 1):                                             # two half-cradles for the 18650
        blk = (cq.Workplane("XY").box(6.0, 21.0, CELL_AXIS_Z - FLOOR + 0.01, centered=(True, False, False))
               .translate((sx * 24.0, -IY / 2, FLOOR - 0.01)))
        groove = cq.Workplane("YZ").workplane(offset=sx * 24.0 - 4).center(CELL_CY, CELL_AXIS_Z).circle(9.4).extrude(8)
        b = b.union(blk.cut(groove))
    usb_z = TP_Z + TP_PCB_T + USB_C_H / 2                           # USB-C opening in the -X end wall
    b = b.cut(cq.Workplane("XY").box(WALL + 2.0, 14.0, 8.0, centered=(False, True, True)).translate((-OX / 2 - 1.0, TP_CY, usb_z)))
    pocket_x0 = IX / 2 - 0.5                                        # slide-switch recess + lever slot in the +X end wall
    pocket_x1 = OX / 2 - SW_WALL_LEFT
    b = b.cut(cq.Workplane("XY").box(pocket_x1 - pocket_x0, SW_POCKET_L, SW_POCKET_W, centered=(False, True, True))
              .translate((pocket_x0, SW_CY, SW_CZ)))
    b = b.cut(cq.Workplane("XY").box(SW_WALL_LEFT + 1.0, SW_SLOT_L, SW_SLOT_W, centered=(False, True, True))
              .translate((pocket_x1 - 0.1, SW_CY, SW_CZ)))
    if NAME:                                                        # embossed name on the front (-Y) wall
        kw = {"fontPath": FONT_PATH} if FONT_PATH else {}
        txt = cq.Workplane("XZ").text(NAME, TEXT_SIZE, TEXT_EMBOSS + 0.2, halign="center", valign="center", **kw)
        b = b.union(txt.translate((0, -OY / 2 + 0.2, Z_LID_IN / 2 + 0.5)))
    return b


def build_lid():
    lid = (cq.Workplane("XY").box(OX, OY, LID_T, centered=(True, True, False))
           .translate((0, 0, Z_LID_IN)).edges("|Z").fillet(CORNER_R))
    holes = [(0.0, 0.0, 3.0)]                                       # speaker grille: centre hole + three rings
    for r, n, dia in ((6.0, 6, 2.6), (10.5, 12, 2.6), (14.5, 16, 2.6)):
        for i in range(n):
            a = 2 * math.pi * i / n
            holes.append((r * math.cos(a), r * math.sin(a), dia))
    for hx, hy, hd in holes:
        lid = lid.cut(cq.Workplane("XY").workplane(offset=Z_LID_IN - 0.01).center(hx, hy).circle(hd / 2).extrude(LID_T + 0.02))
    lid = lid.union(cq.Workplane("XY").workplane(offset=Z_LID_IN - 1.5).circle(DRV_D / 2 + 1.4).circle(DRV_D / 2 + 0.3).extrude(1.51))  # driver locating ring
    for sx in (-1, 1):
        for sy in (-1, 1):
            lid = lid.cut(cq.Workplane("XY").workplane(offset=Z_LID_IN - 0.01).center(sx * BOSS_X, sy * BOSS_Y).circle(CLEAR_D / 2).extrude(LID_T + 0.02))
            lid = lid.cut(cq.Workplane("XY").workplane(offset=Z_TOP - CBORE_DEPTH).center(sx * BOSS_X, sy * BOSS_Y).circle(CBORE_D / 2).extrude(CBORE_DEPTH + 0.01))
    return lid


# =====================================================================================
# BUILD + EXPORT
# =====================================================================================
def rest_on_plane(shape, x, y):
    bb = shape.val().BoundingBox()
    return shape.translate((x - bb.xmin, y - bb.ymin, -bb.zmin))


def overlap(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0


def main(out_dir):
    d_print, d_ref, d_asm = (os.path.join(out_dir, k) for k in ("print", "reference", "assembly"))
    for d in (d_print, d_ref, d_asm):
        os.makedirs(d, exist_ok=True)
    base, lid = build_base(), build_lid()
    amp = amp_board().translate((AMP_CX, AMP_CY, AMP_Z))
    tp = charger_module().translate((TP_CX, TP_CY, TP_Z))
    drv = driver().translate((0, 0, Z_LID_IN))
    cel = cell().rotate((0, 0, 0), (0, 1, 0), 90).translate((-CELL_L / 2, CELL_CY, CELL_AXIS_Z))
    scr, tab = screw(), nickel_tab()
    sw = slide_switch().translate((OX / 2 - SW_WALL_LEFT - SW_H, SW_CY, SW_CZ))

    # sanity checks: nothing should collide
    pairs = [("amp/base", amp, base), ("amp/lid", amp, lid), ("charger/base", tp, base), ("cell/base", cel, base),
             ("cell/lid", cel, lid), ("driver/base", drv, base), ("driver/lid", drv, lid), ("amp/charger", amp, tp),
             ("amp/cell", amp, cel), ("charger/cell", tp, cel), ("driver/cell", drv, cel), ("driver/amp", drv, amp),
             ("driver/charger", drv, tp), ("base/lid", base, lid), ("switch/base", sw, base), ("switch/lid", sw, lid),
             ("switch/driver", sw, drv), ("switch/amp", sw, amp), ("switch/cell", sw, cel)]
    bad = [(n, round(overlap(a, b), 3)) for n, a, b in pairs if overlap(a, b) > 0.001]
    print("collisions:", bad if bad else "none")

    # individual part files (parts 01-06 and 09 share one origin, so they line up when inserted together)
    singles = {
        "01_enclosure_base": (base, d_print), "02_enclosure_lid": (lid, d_print),
        "03_amp_board_DFR0720_MH-M38": (amp, d_ref), "04_driver_40mm_adafruit_3968": (drv, d_ref),
        "05_cell_samsung_INR18650-25R": (cel, d_ref), "06_charger_module_TP4056_USB-C": (tp, d_ref),
        "07_screw_M2x8_self-tapping": (scr, d_ref), "08_nickel_tab_0.15x8x25mm": (tab, d_ref),
        "09_slide_switch_SS12D00G4": (sw, d_ref),
    }
    for name, (shp, d) in singles.items():
        cq.exporters.export(shp, os.path.join(d, name + ".step"))
    # STLs in print orientation: base open side up, lid flipped so the grille faces the bed
    cq.exporters.export(base, os.path.join(d_print, "01_enclosure_base.stl"), tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(rest_on_plane(lid.rotate((0, 0, 0), (1, 0, 0), 180), -OX / 2, -OY / 2),
                        os.path.join(d_print, "02_enclosure_lid.stl"), tolerance=0.02, angularTolerance=0.1)

    # full assembly: screws seated in the lid counterbores (head 0.1 mm proud); nickel tabs omitted
    asm = cq.Assembly(name="speaker_full_assembly")
    for n, shp, col in (("01_enclosure_base", base, (0.85, 0.85, 0.88)), ("02_enclosure_lid", lid, (0.70, 0.72, 0.80)),
                        ("03_amp_board", amp, (0.10, 0.50, 0.20)), ("04_driver", drv, (0.15, 0.15, 0.15)),
                        ("05_cell", cel, (0.20, 0.30, 0.80)), ("06_charger_module", tp, (0.80, 0.50, 0.10))):
        asm.add(shp, name=n, color=cq.Color(*col))
    k = 0
    for sx in (-1, 1):
        for sy in (-1, 1):
            k += 1
            s = scr.rotate((0, 0, 0), (1, 0, 0), 180).translate((sx * BOSS_X, sy * BOSS_Y, Z_TOP + 0.1))
            asm.add(s, name="07_screw_M2x8_%d" % k, color=cq.Color(0.7, 0.7, 0.7))
    asm.add(sw, name="09_slide_switch_SS12D00G4", color=cq.Color(0.8, 0.2, 0.2))
    asm.export(os.path.join(d_asm, "00_full_assembly.step"))

    # flat layout: every part lies on z=0, spread out at full scale (lid flipped, driver face-up)
    lay = cq.Assembly(name="all_parts_layout")
    y2 = 67.0
    placed = [("01_enclosure_base", base, 0, 0), ("02_enclosure_lid_flipped", lid.rotate((0, 0, 0), (1, 0, 0), 180), 95, 0),
              ("05_cell_samsung_INR18650-25R", cel, 0, y2), ("04_driver_40mm_face_up", drv.rotate((0, 0, 0), (1, 0, 0), 180), 75, y2),
              ("03_amp_board_DFR0720_MH-M38", amp, 125, y2), ("06_charger_module_TP4056_USB-C", tp, 125, y2 + 28)]
    placed += [("07_screw_M2x8_%d" % (i + 1), scr, 2 + 8 * i, 92) for i in range(4)]
    placed += [("08_nickel_tab_25mm_%d" % (i + 1), tab, 40, 92 + 11 * i) for i in range(2)]
    placed += [("09_slide_switch_SS12D00G4", sw.rotate((0, 0, 0), (0, 1, 0), -90), 160, 95)]
    for n, shp, x, y in placed:
        lay.add(rest_on_plane(shp, x, y), name=n)
    lay.export(os.path.join(d_asm, "00_layout_flat_all_parts.step"))
    print("wrote %d STEP + 2 STL files under %s" % (len(singles) + 2, os.path.abspath(out_dir)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
