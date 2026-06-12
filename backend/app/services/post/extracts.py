"""Server-side post-processing with PyVista.

TODO(phase-1): read OpenFOAM case (vtkOpenFOAMReader), produce decimated
slice/surface VTP payloads for VTK.js. Never ship full volume meshes to the
browser. ParaView export = write a .foam stub file into the case dir.
"""
