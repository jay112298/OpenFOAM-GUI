"""Airfoil external-aerodynamics template: a pre-filled case spec.

Field metadata (label, unit, range, help) drives the GUI form and the
educational layer.
"""

AIRFOIL_TEMPLATE = {
    "id": "airfoil",
    "name": "Airfoil (external aero)",
    "domain": "aero",
    "description": "2D external aerodynamics around a NACA airfoil. Steady "
    "incompressible RANS. Computes lift/drag coefficients.",
    "spec": {
        "domain": "aero",
        "geometry": {
            "kind": "naca4",
            "parameters": {"designation": "0012", "chord": 1.0},
        },
        "physics": {
            "flow_type": "incompressible",
            "time_treatment": "steady",
            "turbulence_model": "kOmegaSST",
            "fluid": {"name": "air"},
            "reference": {
                "velocity": 30.0,
                "angle_of_attack": 0.0,
                "turbulence_intensity": 0.01,
            },
        },
        "mesh": {
            "strategy": "gmsh",
            "parameters": {
                "farfield_radius": 50.0,
                "boundary_layers": False,
                "n_layers": 15,
                "target_yplus": 30.0,
            },
        },
        "numerics": {"solver": "simpleFoam", "end_time": 2000, "write_interval": 200, "n_procs": 1},
    },
    "fields": [
        {"key": "geometry.parameters.designation", "label": "NACA designation", "type": "text", "help": "4- or 5-digit code, e.g. 0012, 4412, 23012."},
        {"key": "geometry.parameters.chord", "label": "Chord", "unit": "m", "type": "number", "min": 0.01, "help": "Reference chord length."},
        {"key": "physics.reference.velocity", "label": "Freestream speed", "unit": "m/s", "type": "number", "min": 0.1, "help": "Inflow velocity magnitude."},
        {"key": "physics.reference.angle_of_attack", "label": "Angle of attack", "unit": "deg", "type": "number", "min": -20, "max": 20, "help": "Applied by rotating the freestream, not the mesh."},
        {"key": "physics.reference.turbulence_intensity", "label": "Turbulence intensity", "type": "number", "min": 0.001, "max": 0.2, "help": "Fraction (0.01 = 1%). External aero: 0.1–1%."},
        {"key": "physics.turbulence_model", "label": "Turbulence model", "type": "select", "options": ["kOmegaSST", "kOmegaSSTLM", "kEpsilon", "realizableKE"], "help": "kOmegaSST is a robust default; kOmegaSSTLM adds transition."},
        {"key": "mesh.parameters.farfield_radius", "label": "Far-field radius", "unit": "chords", "type": "number", "min": 5, "help": "Recommended 40–50c. The main drag-accuracy lever — small domains inflate pressure drag."},
        {"key": "mesh.parameters.boundary_layers", "label": "Boundary layers (opt-in)", "type": "bool", "help": "Experimental: snappy prism layers for a resolved y+~1 wall. Reliability depends on layer/base-cell sizing."},
        {"key": "mesh.parameters.n_layers", "label": "Number of layers", "type": "number", "min": 1, "max": 40, "help": "Prism layers when enabled. Recommended 10–20."},
        {"key": "mesh.parameters.target_yplus", "label": "Target y+", "type": "number", "min": 0.5, "help": "30–100 for the default wall-function mesh; ~1 with boundary layers."},
        {"key": "numerics.end_time", "label": "Max iterations", "type": "number", "min": 100, "help": "Steady solver iteration cap (endTime)."},
        {"key": "numerics.n_procs", "label": "CPU cores", "type": "number", "min": 1, "help": "Parallel solve via decomposePar + mpirun."},
    ],
}


def _compressible_spec() -> dict:
    """Same airfoil pipeline, solved with rhoSimpleFoam at a high-subsonic speed."""
    import copy

    spec = copy.deepcopy(AIRFOIL_TEMPLATE["spec"])
    spec["physics"]["flow_type"] = "compressible"
    spec["physics"]["reference"].update(
        {
            "velocity": 170.0,        # ~Mach 0.5 at sea level
            "temperature": 288.15,    # K
            "pressure": 101325.0,     # Pa
        }
    )
    spec["numerics"]["solver"] = "rhoSimpleFoam"
    return spec


AIRFOIL_COMPRESSIBLE_TEMPLATE = {
    "id": "airfoil_compressible",
    "name": "Airfoil — compressible (high speed)",
    "domain": "aero",
    "description": "2D external aerodynamics at high subsonic speed. Solves the energy "
    "equation with rhoSimpleFoam, so density and temperature vary through the flow.",
    "spec": _compressible_spec(),
    "fields": AIRFOIL_TEMPLATE["fields"]
    + [
        {"key": "physics.reference.temperature", "label": "Freestream temperature", "unit": "K", "type": "number", "min": 100, "help": "Sea-level standard is 288.15 K. Sets the speed of sound, so it sets Mach."},
        {"key": "physics.reference.pressure", "label": "Freestream pressure", "unit": "Pa", "type": "number", "min": 1000, "help": "Sea-level standard is 101325 Pa. With temperature this fixes the density."},
    ],
}
