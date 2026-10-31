"""First-order thermal sizing for a proposed 4-inch semiconductor hot plate.

This is a screening model, not a thermal FEA or measured result.
Run from the repository root:
    python3 calcs/thermal_calc.py
"""
import math

SIGMA = 5.670374419e-8  # Stefan-Boltzmann constant, W m^-2 K^-4

# Geometry and material assumptions
DIAMETER_M = 0.160
THICKNESS_M = 0.020
RHO_AL6061 = 2700.0      # kg/m^3
CP_AL6061 = 896.0        # J/(kg K)
K_AL6061 = 167.0         # W/(m K), approximate room-temperature value

T_AMBIENT_C = 25.0
T_SET_C = 400.0
EMISSIVITY = 0.20        # assumed; actual surface finish changes this
H_CONVECTION = 8.0       # W/(m^2 K), rough natural-convection assumption
INSULATION_K = 0.03      # W/(m K), assumed insulation conductivity
INSULATION_THICKNESS_M = 0.025
RAMP_MIN = 20.0
WAFER_DIAMETER_M = 0.1016
WAFER_THICKNESS_M = 525e-6
RHO_SILICON = 2330.0
CP_SILICON = 700.0       # approximate J/(kg K)

R = DIAMETER_M / 2
A_TOP = math.pi * R**2
A_SIDE = 2 * math.pi * R * THICKNESS_M
V = A_TOP * THICKNESS_M
MASS = RHO_AL6061 * V
HEAT_CAPACITY = MASS * CP_AL6061
ENERGY_J = HEAT_CAPACITY * (T_SET_C - T_AMBIENT_C)
AVERAGE_RAMP_POWER_W = ENERGY_J / (RAMP_MIN * 60)

T_HOT_K = T_SET_C + 273.15
T_AMB_K = T_AMBIENT_C + 273.15
Q_RAD_PER_M2 = EMISSIVITY * SIGMA * (T_HOT_K**4 - T_AMB_K**4)
Q_CONV_PER_M2 = H_CONVECTION * (T_SET_C - T_AMBIENT_C)

TOP_LOSS_W = A_TOP * (Q_RAD_PER_M2 + Q_CONV_PER_M2)
SIDE_LOSS_W = A_SIDE * (Q_RAD_PER_M2 + Q_CONV_PER_M2)
BOTTOM_LOSS_W = (INSULATION_K / INSULATION_THICKNESS_M) * A_TOP * (T_SET_C - T_AMBIENT_C)
STANDOFF_LOSS_W = 5.0  # placeholder estimate; depends on geometry/material
TOTAL_LOSS_W = TOP_LOSS_W + SIDE_LOSS_W + BOTTOM_LOSS_W + STANDOFF_LOSS_W

# Approximate radial temperature drop for a disk with side loss.
# This is only a simplified conduction estimate and not a uniformity prediction.
R_WAFER = WAFER_DIAMETER_M / 2
RADIAL_DROP_C = SIDE_LOSS_W / (2 * math.pi * K_AL6061 * THICKNESS_M) * math.log(R / R_WAFER)

wafer_volume = math.pi * R_WAFER**2 * WAFER_THICKNESS_M
wafer_mass = RHO_SILICON * wafer_volume
wafer_heat_capacity = wafer_mass * CP_SILICON

print("FIRST-ORDER HOT-PLATE THERMAL SIZING — NOT VALIDATED PERFORMANCE")
print(f"Plate: {DIAMETER_M*1000:.0f} mm diameter x {THICKNESS_M*1000:.0f} mm")
print(f"Volume: {V*1e6:.1f} cm^3")
print(f"Plate mass: {MASS:.3f} kg")
print(f"Plate heat capacity: {HEAT_CAPACITY:.1f} J/K")
print(f"Energy from {T_AMBIENT_C:.0f} C to {T_SET_C:.0f} C: {ENERGY_J/1000:.1f} kJ")
print(f"Average ideal power for {RAMP_MIN:.0f}-minute ramp (ignores losses): {AVERAGE_RAMP_POWER_W:.1f} W")
print(f"Estimated losses at {T_SET_C:.0f} C: top={TOP_LOSS_W:.1f} W, side={SIDE_LOSS_W:.1f} W, bottom={BOTTOM_LOSS_W:.1f} W, standoffs={STANDOFF_LOSS_W:.1f} W")
print(f"Total estimated steady-state loss: {TOTAL_LOSS_W:.1f} W")
print(f"Approximate radial drop from wafer edge (r={R_WAFER*1000:.1f} mm) to plate edge: {RADIAL_DROP_C:.2f} C (simplified model only)")
print(f"4-inch silicon wafer estimate: mass={wafer_mass*1000:.1f} g, heat capacity={wafer_heat_capacity:.1f} J/K")
print("Installed heater power: 1,000 W nominal (4 x 250 W); controller must limit ramp and prevent overshoot.")
print("Do not claim ±0.5 C uniformity or repeatability until the validation plan passes.")
