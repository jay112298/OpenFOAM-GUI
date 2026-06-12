"""Unit conversion layer: GUI accepts mm/in/RPM/bar/degC, OpenFOAM gets strict SI.

TODO(phase-1): conversion table + pydantic value type carrying (value, unit),
converted once at the API boundary. Nothing inside services ever sees non-SI.
"""
