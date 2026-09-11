"""Parametric axial-fan / compressor blade.

The blade is built from NACA sections stacked along the radius. What makes it
usable by a non-expert is that the **twist is not typed in — it is derived from
the velocity triangle** at every radius:

    U(r)  = omega * r                 blade speed
    beta1 = atan(U / Va)              relative inflow angle, from the axial dir
    gamma = beta1 - incidence         blade stagger (chord line)

so the blade is automatically twisted to meet the flow at a constant incidence
from hub to tip. Get the RPM or the flow wrong and the reported incidence /
solidity tell you immediately.

Coordinate convention (shared with the generator and the MRF setup):
  +z  axial, inlet -> outlet
  rotation about +z, omega > 0, so the blade moves toward +theta

For a *fan* (work added to the fluid) the blade must turn the relative flow
toward +theta, which means the section camber is mirrored relative to the usual
airfoil convention — see CAMBER_SIGN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.services.geometry import naca

# A standard NACA mean line bows toward +y, which on this blade would turn the
# relative flow toward -theta: that extracts work (a turbine). Mirroring the
# section puts the concave (pressure) face toward +theta, the direction of
# rotation, which is what a fan/compressor rotor needs.
CAMBER_SIGN = -1.0

RPM_TO_RAD_S = 2.0 * math.pi / 60.0


@dataclass
class BladeSpec:
    designation: str = "4412"
    n_blades: int = 6
    hub_radius: float = 0.06       # [m]
    tip_radius: float = 0.15       # [m]
    chord: float = 0.05            # [m], constant along the span
    rpm: float = 3000.0
    axial_velocity: float = 12.0   # design through-flow [m/s]
    incidence: float = 4.0         # [deg] chord set below the relative inflow angle
    n_sections: int = 21           # radial stations in the lofted surface
    n_points: int = 90             # points per surface of each section

    @property
    def omega(self) -> float:
        """Shaft speed [rad/s]."""
        return self.rpm * RPM_TO_RAD_S

    @property
    def span(self) -> float:
        return self.tip_radius - self.hub_radius

    @property
    def mean_radius(self) -> float:
        return 0.5 * (self.hub_radius + self.tip_radius)

    @property
    def sector_angle(self) -> float:
        """Angular width of one passage [rad]."""
        return 2.0 * math.pi / self.n_blades

    @property
    def tip_speed(self) -> float:
        return self.omega * self.tip_radius

    @property
    def flow_coefficient(self) -> float:
        """phi = Va / U_tip. Axial fans typically run 0.15–0.6."""
        return self.axial_velocity / self.tip_speed if self.tip_speed else float("inf")


@dataclass
class BladeSection:
    """Velocity-triangle state at one radius. Reported in the GUI."""

    radius: float
    blade_speed: float      # U = omega r [m/s]
    relative_angle: float   # beta1, from axial [deg]
    stagger: float          # gamma, from axial [deg]
    relative_speed: float   # |W| [m/s]
    pitch: float            # blade-to-blade spacing at this radius [m]
    solidity: float         # chord / pitch
    tangential_extent: float  # how far the staggered chord reaches around [m]


def section_at(spec: BladeSpec, radius: float) -> BladeSection:
    u = spec.omega * radius
    beta1 = math.degrees(math.atan2(u, spec.axial_velocity))
    gamma = beta1 - spec.incidence
    pitch = 2.0 * math.pi * radius / spec.n_blades
    return BladeSection(
        radius=radius,
        blade_speed=u,
        relative_angle=beta1,
        stagger=gamma,
        relative_speed=math.hypot(u, spec.axial_velocity),
        pitch=pitch,
        solidity=spec.chord / pitch if pitch else float("inf"),
        tangential_extent=abs(spec.chord * math.sin(math.radians(gamma))),
    )


def sections(spec: BladeSpec, n: int = 5) -> list[BladeSection]:
    """Velocity-triangle summary from hub to tip (for the GUI table)."""
    radii = np.linspace(spec.hub_radius, spec.tip_radius, n)
    return [section_at(spec, float(r)) for r in radii]


def _section_points(spec: BladeSpec, radius: float, stagger_radius: float) -> np.ndarray:
    """One closed section ring in Cartesian coordinates, at `radius`.

    `stagger_radius` is the radius whose velocity triangle sets the twist. It
    differs from `radius` only for the small overhang sections that poke through
    the hub and shroud, so the overhang is a straight continuation of the blade.
    """
    af = naca.generate(spec.designation, chord=spec.chord, n=spec.n_points)
    # the ring closes on itself: first and last point are both the (closed) TE
    x = af.x[:-1] - 0.5 * spec.chord          # stack about mid-chord
    y = CAMBER_SIGN * af.y[:-1]
    gamma = math.radians(section_at(spec, stagger_radius).stagger)
    cg, sg = math.cos(gamma), math.sin(gamma)

    # chord direction  c = ( cos g, -sin g)  in (axial, tangential)
    # section normal   n = ( sin g,  cos g)
    z = x * cg + y * sg
    t = -x * sg + y * cg
    theta = t / radius
    return np.column_stack([radius * np.cos(theta), radius * np.sin(theta), z])


def section_outline(spec: BladeSpec, radius: float) -> list[list[float]]:
    """The section at `radius`, unrolled onto a flat (axial, tangential) plane.

    This is the cascade view: cut the annulus at that radius, unwrap the
    cylinder, and you see the blade row as a row of 2D sections one pitch
    apart. Returned closed, in metres.
    """
    ring = _section_points(spec, radius, radius)
    return [[float(p[2]), float(radius * math.atan2(p[1], p[0]))] for p in ring]


def surface(spec: BladeSpec, overhang: float = 0.03) -> np.ndarray:
    """Lofted blade surface as an (n_sections, n_ring, 3) point array.

    The loft is extended `overhang` (fraction of span) past the hub and the
    shroud so the surface cleanly crosses both walls and snappyHexMesh has a
    closed body to cut from the annulus.
    """
    d = overhang * spec.span
    radii = np.linspace(spec.hub_radius - d, spec.tip_radius + d, spec.n_sections)
    rings = [
        _section_points(spec, float(r), float(np.clip(r, spec.hub_radius, spec.tip_radius)))
        for r in radii
    ]
    return np.stack(rings)


def _rotate_z(points: np.ndarray, angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    out = points.copy()
    out[..., 0] = points[..., 0] * c - points[..., 1] * s
    out[..., 1] = points[..., 0] * s + points[..., 1] * c
    return out


def _triangles(loft: np.ndarray) -> np.ndarray:
    """Close the lofted surface into a triangle soup: side quads + end caps."""
    n_sec, n_ring, _ = loft.shape
    tris: list[np.ndarray] = []

    for s in range(n_sec - 1):
        a, b = loft[s], loft[s + 1]
        nxt = np.roll(np.arange(n_ring), -1)
        # quad (a[i], a[i+1], b[i+1], b[i]) -> two triangles
        tris.append(np.stack([a, a[nxt], b[nxt]], axis=1))
        tris.append(np.stack([a, b[nxt], b], axis=1))

    for ring, flip in ((loft[0], True), (loft[-1], False)):
        centre = ring.mean(axis=0)
        nxt = np.roll(np.arange(len(ring)), -1)
        fan = np.stack([np.tile(centre, (len(ring), 1)), ring, ring[nxt]], axis=1)
        tris.append(fan[:, ::-1] if flip else fan)

    return np.concatenate(tris)


def export_stl(spec: BladeSpec, path: Path, n_copies: int = 3) -> Path:
    """Write the blade as an STL, repeated at the blade pitch.

    `n_copies` places the blade at theta = -pitch, 0, +pitch. A highly staggered
    or high-solidity blade reaches across the periodic plane of its own passage;
    writing the neighbours means the two periodic faces get cut identically and
    the passage stays physically periodic. Copies that fall outside the sector
    are simply never touched by the mesher.
    """
    loft = surface(spec)
    offsets = [0.0]
    for i in range(1, n_copies):
        k = (i + 1) // 2 * (1 if i % 2 else -1)
        offsets.append(k * spec.sector_angle)

    tris = np.concatenate([_triangles(_rotate_z(loft, a)) for a in offsets])
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    # binary STL: the ASCII form of this loft runs to ~6 MB per case
    record = np.zeros(len(tris), dtype=_STL_FACET)
    record["normal"] = normals
    record["v"] = tris
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(b"blade".ljust(80, b"\0"))
        fh.write(np.uint32(len(tris)).tobytes())
        fh.write(record.tobytes())
    return path


_STL_FACET = np.dtype(
    [("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")], align=False
)
