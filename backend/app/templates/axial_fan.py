"""Axial fan rotor template: one blade passage solved in a rotating frame.

Field metadata drives the GUI form and the educational layer, same as the
airfoil template. The defaults describe a small ducted fan — 300 mm casing,
6 blades, 3000 rpm — which meshes in a few seconds and solves in about two
minutes on a laptop.
"""

AXIAL_FAN_TEMPLATE = {
    "id": "axial_fan",
    "name": "Axial fan rotor (MRF passage)",
    "domain": "turbo",
    "description": "One blade passage of an axial fan or compressor rotor, solved steady "
    "in a rotating frame (MRF) with rotational cyclicAMI periodics. Blade twist is derived "
    "from the velocity triangle; reports flow rate, total pressure rise, torque and efficiency.",
    "spec": {
        "domain": "turbo",
        "geometry": {
            "kind": "axial_blade",
            "parameters": {
                "designation": "4412",
                "n_blades": 6,
                "hub_radius": 0.06,
                "tip_radius": 0.15,
                "chord": 0.05,
                "incidence": 4.0,
            },
        },
        "physics": {
            "flow_type": "incompressible",
            "time_treatment": "steady",
            "turbulence_model": "kOmegaSST",
            "fluid": {"name": "air"},
            "reference": {
                "rpm": 3000.0,
                "axial_velocity": 12.0,
                "turbulence_intensity": 0.05,
            },
        },
        "mesh": {
            "strategy": "sector-snappy",
            "parameters": {
                "cells_per_chord": 8,
                "refinement_level": 2,
                "inlet_length": 2.0,
                "outlet_length": 4.0,
                "boundary_layers": False,
                "n_layers": 8,
                "target_yplus": 50.0,
            },
        },
        "numerics": {"solver": "simpleFoam", "end_time": 1500, "write_interval": 250, "n_procs": 1},
    },
    "fields": [
        {"key": "geometry.parameters.designation", "label": "Blade section", "type": "text", "help": "NACA 4- or 5-digit code used at every radius. 4412 is a good cambered fan section."},
        {"key": "geometry.parameters.n_blades", "label": "Number of blades", "type": "number", "min": 3, "max": 40, "help": "Sets the passage width: the sector solved is 360/n degrees."},
        {"key": "geometry.parameters.hub_radius", "label": "Hub radius", "unit": "m", "type": "number", "min": 0.005, "help": "Inner wall of the annulus. Hub/tip ratio 0.3–0.7 is typical."},
        {"key": "geometry.parameters.tip_radius", "label": "Tip radius", "unit": "m", "type": "number", "min": 0.01, "help": "Casing radius. Tip speed = rpm x this, and it sets the tip Mach number."},
        {"key": "geometry.parameters.chord", "label": "Blade chord", "unit": "m", "type": "number", "min": 0.002, "help": "Constant along the span. Chord/pitch (solidity) near 1 at the hub is a good target."},
        {"key": "geometry.parameters.incidence", "label": "Design incidence", "unit": "deg", "type": "number", "min": -10, "max": 20, "help": "How far the chord sits below the relative inflow angle. 2–6° is the usual design band."},
        {"key": "physics.reference.rpm", "label": "Shaft speed", "unit": "rpm", "type": "number", "min": 1, "help": "Rotation about the flow axis. Drives the blade twist and the MRF zone."},
        {"key": "physics.reference.axial_velocity", "label": "Design axial velocity", "unit": "m/s", "type": "number", "min": 0.1, "help": "Through-flow at the inlet. With the tip speed this is the flow coefficient."},
        {"key": "physics.reference.turbulence_intensity", "label": "Turbulence intensity", "type": "number", "min": 0.001, "max": 0.2, "help": "Fraction (0.05 = 5%). Ducted machines are typically 3–10%."},
        {"key": "physics.turbulence_model", "label": "Turbulence model", "type": "select", "options": ["kOmegaSST", "kEpsilon", "realizableKE"], "help": "kOmegaSST handles adverse pressure gradients on the blade best."},
        {"key": "mesh.parameters.cells_per_chord", "label": "Cells per chord", "type": "number", "min": 4, "max": 40, "help": "Background cell size = chord / this. Raise it for accuracy, at a cell-count cost."},
        {"key": "mesh.parameters.refinement_level", "label": "Blade refinement level", "type": "number", "min": 1, "max": 4, "help": "snappyHexMesh halves the cell size this many times at the blade surface."},
        {"key": "mesh.parameters.inlet_length", "label": "Inlet duct", "unit": "chords", "type": "number", "min": 0.5, "help": "Upstream length. At least 1.5–2 so the inlet BC is clear of the blade."},
        {"key": "mesh.parameters.outlet_length", "label": "Outlet duct", "unit": "chords", "type": "number", "min": 1, "help": "Downstream length. At least 3–4 so the swirling wake settles before the outlet."},
        {"key": "mesh.parameters.target_yplus", "label": "Target y+", "type": "number", "min": 0.5, "help": "30–100 for the default wall-function mesh; ~1 with prism layers."},
        {"key": "numerics.end_time", "label": "Max iterations", "type": "number", "min": 100, "help": "Steady solver iteration cap. 1000–2000 is usually enough for one passage."},
        {"key": "numerics.n_procs", "label": "CPU cores", "type": "number", "min": 1, "help": "Parallel solve via decomposePar + mpirun."},
    ],
}
