"""y+ -> first cell height calculator.

TODO(phase-1): flat-plate correlation based estimate:
  Cf = 0.058 * Re^-0.2, tau_w = Cf * 0.5 * rho * U^2,
  u_tau = sqrt(tau_w / rho), y1 = yplus_target * nu / u_tau
Feeds snappyHexMesh boundary-layer settings directly.
"""
