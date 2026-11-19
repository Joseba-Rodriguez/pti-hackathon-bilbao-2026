"""Rampa de gravedad (cargador de tomas) y vasito para el proyecto Esperanza.

Unidades en mm. Cambia los parámetros de abajo y vuelve a ejecutar para regenerar los STL:
    pip install trimesh shapely manifold3d
    python piezas/make_stl.py piezas/stl
"""
import math

import numpy as np
import trimesh
from trimesh.creation import cylinder, box, extrude_polygon
from shapely.geometry import Polygon

# ---------------- vasito ----------------
CUP_D = 38.0          # diámetro del cuerpo (lo que agarra la pinza)
CUP_H = 55.0          # altura total
CUP_WALL = 1.8
CUP_BOTTOM = 2.0
RIM_D = 41.0          # anillo de color superior (no deja que el vaso resbale entre los dedos)
RIM_H = 6.0
FOOT_D = 35.0         # pie ligeramente más estrecho: menos rozamiento en la rampa
FOOT_H = 1.0
RIBS = 24             # nervios verticales de agarre bajo el anillo
RIB_W, RIB_D = 1.2, 0.5
RIB_Z0, RIB_Z1 = 18.0, CUP_H - RIM_H

# ---------------- rampa ----------------
GAP = 5.0                       # holgura lateral total entre el anillo del vaso y las paredes
W_IN = RIM_D + GAP              # anchura interior del canal
WALL = 3.0
POCKET_L = RIM_D + 4            # bolsillo delantero donde la pinza recoge el vaso
POCKET_ANGLE = 3.0              # leve inclinación hacia el tope, para que el vaso quede siempre apoyado en él
BLEND_R = 40.0                  # radio de la curva de transición entre bolsillo y rampa
SLOPE_L = 165.0                 # tramo inclinado (caben unos 4 vasos más)
ANGLE = 10.0                    # grados. Debe superar el ángulo de deslizamiento medido con la probeta + 4°.
                                # Era 22: en la simulación los vasitos, inclinados como la pendiente, empujan al
                                # primero por el anillo y no queda en una postura fija. Con 10° sí (±3 mm), pero
                                # el vasito debe deslizar a ≤6° en la probeta (cinta de PTFE o PETG liso).
FLOOR0 = 6.0                    # altura del suelo en el bolsillo
SIDE_H = 22.0                   # altura de las paredes por encima del suelo
CURB_H = 25.0                   # tope delantero por encima del suelo del bolsillo (era 7: el primer vasito se
                                # volcaba hacia delante por encima). El vasito sale de lado, no por encima del tope.
LIP_H = 3.0                     # labios laterales bajos en el bolsillo (dejan sitio a los dedos)
SEG = 128


def cup():
    body = cylinder(radius=CUP_D / 2, height=CUP_H - FOOT_H, sections=SEG)
    body.apply_translation([0, 0, FOOT_H + (CUP_H - FOOT_H) / 2])
    foot = cylinder(radius=FOOT_D / 2, height=FOOT_H, sections=SEG)
    foot.apply_translation([0, 0, FOOT_H / 2])
    rim = cylinder(radius=RIM_D / 2, height=RIM_H, sections=SEG)
    rim.apply_translation([0, 0, CUP_H - RIM_H / 2])
    ribs = []
    for k in range(RIBS):
        ang = 2 * math.pi * k / RIBS
        rib = box([RIB_W, RIB_D * 2, RIB_Z1 - RIB_Z0])
        rib.apply_translation([0, CUP_D / 2, (RIB_Z0 + RIB_Z1) / 2])
        rib.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        ribs.append(rib)
    outer = trimesh.boolean.union([body, foot, rim] + ribs, engine="manifold")
    inner_r = CUP_D / 2 - CUP_WALL
    cavity = cylinder(radius=inner_r, height=CUP_H, sections=SEG)
    cavity.apply_translation([0, 0, CUP_BOTTOM + CUP_H / 2])
    # chaflán interior en la boca, para que la pastilla salga sin engancharse
    cone = trimesh.creation.cone(radius=inner_r + 1.2, height=8, sections=SEG)
    cone.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    cone.apply_translation([0, 0, CUP_H + 0.01])
    return trimesh.boolean.difference([outer, cavity, cone], engine="manifold")


def profile_solid(points_xz, width, y0):
    """Extruye un perfil lateral (x, z) a lo ancho (y)."""
    m = extrude_polygon(Polygon(points_xz), width)
    # extrude_polygon extruye en +Z sobre el plano XY: rotamos para que el perfil quede en XZ
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    m.apply_translation([0, y0 + width, 0])
    return m


def floor_profile():
    """Puntos (x, z) de la superficie del suelo, de delante (x=0) a atrás, con curva de transición."""
    a0, a1 = math.radians(POCKET_ANGLE), math.radians(ANGLE)
    pts = [(0.0, FLOOR0)]
    # tramo del bolsillo hasta el inicio de la curva
    half = BLEND_R * math.tan((a1 - a0) / 2)
    xb = POCKET_L - half * math.cos(a0)
    pts.append((xb, FLOOR0 + xb * math.tan(a0)))
    # arco de transición
    cx = xb - BLEND_R * math.sin(a0)
    cz = pts[-1][1] + BLEND_R * math.cos(a0)
    for k in range(1, 13):
        ang = a0 + (a1 - a0) * k / 12
        pts.append((cx + BLEND_R * math.sin(ang), cz - BLEND_R * math.cos(ang)))
    x2, z2 = pts[-1]
    L = POCKET_L + SLOPE_L
    pts.append((L, z2 + (L - x2) * math.tan(a1)))
    return pts


def ramp():
    fp = floor_profile()
    L = fp[-1][0]
    ztop = fp[-1][1]
    W = W_IN + 2 * WALL
    base = profile_solid([(0, 0), (L, 0)] + fp[::-1], W, 0)
    walls = [(x, z + SIDE_H) for x, z in fp if x >= POCKET_L - 0.01]
    wall_pts = [(POCKET_L, 0), (L, 0)] + walls[::-1]
    left = profile_solid(wall_pts, WALL, 0)
    right = profile_solid(wall_pts, WALL, W - WALL)
    back = box([WALL, W, ztop + SIDE_H])
    back.apply_translation([L + WALL / 2, W / 2, (ztop + SIDE_H) / 2])
    curb = box([WALL, W, FLOOR0 + CURB_H])
    curb.apply_translation([-WALL / 2, W / 2, (FLOOR0 + CURB_H) / 2])
    lips = []
    for y in (WALL / 2, W - WALL / 2):
        lip = box([POCKET_L, WALL, FLOOR0 + LIP_H])
        lip.apply_translation([POCKET_L / 2, y, (FLOOR0 + LIP_H) / 2])
        lips.append(lip)
    solid = trimesh.boolean.union([base, left, right, back, curb] + lips, engine="manifold")
    # marca de centrado en el bolsillo: círculo rebajado 0,6 mm donde se apoya el vaso
    mark = cylinder(radius=FOOT_D / 2 + 1, height=1.2, sections=SEG)
    mark.apply_translation([POCKET_L / 2, W / 2, FLOOR0 + POCKET_L / 2 * math.tan(math.radians(POCKET_ANGLE))])
    # dos orejetas delanteras con agujero para tornillo o brida
    tabs = []
    for y in (-14, W + 14):
        tab = box([24, 24, 4])
        tab.apply_translation([12, y, 2])
        hole = cylinder(radius=2.2, height=10, sections=48)
        hole.apply_translation([12, y, 2])
        tabs.append(trimesh.boolean.difference([tab, hole], engine="manifold"))
    solid = trimesh.boolean.union([solid] + tabs, engine="manifold")
    solid = trimesh.boolean.difference([solid, mark], engine="manifold")
    return solid, dict(L=L + 2 * WALL, W=W + 28 + 24, H=ztop + SIDE_H, cap=1 + int(SLOPE_L // RIM_D), angle=ANGLE)


def coupon():
    """Probeta para medir el ángulo al que desliza el vasito: misma superficie que el suelo de la rampa."""
    plate = box([120, W_IN + 2 * WALL, 3])
    plate.apply_translation([60, (W_IN + 2 * WALL) / 2, 1.5])
    rails = []
    for y in (WALL / 2, W_IN + 1.5 * WALL):
        r = box([120, WALL, 10])
        r.apply_translation([60, y, 5])
        rails.append(r)
    return trimesh.boolean.union([plate] + rails, engine="manifold")


if __name__ == "__main__":
    import sys
    out = sys.argv[1]
    c = cup()
    c.export(f"{out}/vasito_esperanza.stl")
    coupon().export(f"{out}/probeta_rozamiento.stl")
    r, info = ramp()
    r.export(f"{out}/rampa_cargador_esperanza.stl")
    for name, m in (("vasito", c), ("rampa", r)):
        ext = m.bounds[1] - m.bounds[0]
        print(name, "watertight", m.is_watertight, "volumen cm3 %.1f" % (m.volume / 1000), "medidas mm", np.round(ext, 1))
    print("capacidad aprox. de la rampa:", info["cap"], "vasitos; ángulo", info["angle"])
