# KUSUMURU SURESH KUMAR — HackerFab IITB Submission
## Part 2B: Design proposal for a 4-inch semiconductor-processing hot plate

**Status:** Engineering proposal with first-order calculations and a validation plan. This is not a fabricated or experimentally validated instrument.

- **Part 1 — Motivation:** [`Part 1 Motivation.pdf`](Motivation.pdf)
- **Part 2B — Detailed engineering report:** [`Part 2B Hot plate design.pdf`](Design%20a%20Hot%20plate%20for%20semiconductor%20processing.pdf)
- **Video walkthrough (10 minutes maximum):** *Add the published YouTube or Loom URL before submission.*

## 1. Motivation and design choice

A semiconductor-processing hot plate must do more than reach a high temperature. It must control temperature accurately, maintain uniformity across a 4-inch wafer, repeat process runs consistently, and preserve surface flatness after thermal cycling. This proposal uses a 160 mm diameter heat-spreader plate, four nominal 250 W cartridge heaters arranged in two independently controlled zones, two 4-wire Pt100 sensors, insulation, and independent hardware protection.

A thick aluminium plate is a cost-conscious prototype starting point because it spreads heat laterally and is straightforward to machine. The main risk is distortion at elevated temperature and loss of the original 6061-T6 temper. Therefore, the flatness requirement is a validation gate, not a claim of success. A qualified workshop must approve the material condition, thermal treatment and final machining route.

## 2. Design overview

- **Finished plate target:** Ø160 × 20 mm.
- **Heater power:** 4 × 250 W = 1 kW nominal; two 500 W zones.
- **Temperature feedback:** two 4-wire Pt100 sensors and an RTD interface.
- **Control:** ramp-limited, two-zone PID with data logging.
- **Independent safety:** over-temperature cut-out, contactor, emergency stop, protective earthing, overcurrent protection and guarded mains terminals.
- **Thermal management:** underside and side insulation, plus repeatable wafer supports.
- **Validation:** accuracy, wafer-area uniformity, run-to-run repeatability and flatness are tested separately.

## 3. First-order calculation results

Run `python3 calcs/thermal_calc.py` from the repository root.

The model estimates about 1.09 kg plate mass, 973 J/K heat capacity, 365 kJ to heat from 25 °C to 400 °C, and 304 W ideal average power for a 20-minute ramp before losses. Estimated 400 °C losses are around 172 W under the stated assumptions. These figures support considering 1 kW installed power, but do not prove the ramp time, uniformity or repeatability.

## 4. How the specifications will be tested

- **Accuracy:** compare setpoint to a calibrated reference at 100, 200, 300 and 400 °C; absolute error must be below 5 °C.
- **Uniformity:** map the wafer footprint at multiple points; maximum minus minimum must be no more than 1.0 °C at each tested setpoint.
- **Repeatability:** conduct ten repeat runs with a fixed ramp/soak and wafer position; report max–min and standard deviation.
- **Flatness:** measure the top surface at multiple points after machining and after thermal cycling; state the tolerance definition and measurement uncertainty.

The consolidated engineering report describes the proposed validation approach. Detailed acceptance criteria must be finalised before physical testing.

## 5. Main challenges and mitigation

1. **Plate warpage at 400 °C:** use a qualified material/thermal-conditioning route, finish-grind after stress relief, cycle the assembly and re-measure.
2. **Edge temperature drop:** use two zones, insulation and a wafer-area temperature map to tune the edge zone.
3. **Sensor bias and drift:** use 4-wire RTDs, reference calibration, fixed sensor depth and periodic drift checks.
4. **Repeatability:** standardise ramp rate, soak criterion, wafer support and measurement protocol.
5. **Mains and hot-surface hazards:** use an independent hardware cutoff, contactor, protective earth and correctly rated protection; obtain a qualified electrical review.

## 6. Budget and limitations

The current budgetary BOM estimate is approximately ₹46,700 before tax, shipping, labour, certification and rework. All costs require supplier/workshop quotes. The thermal model is first-order; final heater geometry requires verification against the dimensioned drawing and may need FEA or iterative testing. No performance specification should be described as achieved until measured data demonstrates it.

## Repository contents

- `Motivation.pdf` — Part 1 Motivation statement (linked above as “Part 1 Motivation.pdf”).
- `Design a Hot plate for semiconductor processing.pdf` — consolidated Part 2B engineering report (linked above as “Part 2B Hot plate design.pdf”).
- `CAD/HackerFab_Hot_Plate_AllInOne.FCMacro` — FreeCAD macro.
- `CAD/HackerFab_Hot_Plate_Desin.FCStd` — FreeCAD model (filename retained as supplied).
- `CAD/Hot Plate Dimensioned Concept Drawing.FCStd` — FreeCAD drawing model.
- `CAD/Hot Plate Dimensioned Concept Drawing_FINAL - Hot Plate Dimensioned Concept Drawing__.pdf` — exported dimensioned concept drawing.
- `CAD/Hot_Plate_Drawing_FINAL.FCMacro` — FreeCAD drawing macro.
- `calcs/thermal_calc.py` — reproducible first-order calculation script.
- `calcs/thermal_results.txt` — calculation output.

## Before submission

1. Replace the video placeholder near the top with the published YouTube or Loom URL. Keep the video at or below 10 minutes.
2. Confirm that this README and every linked file are present in the public GitHub repository.
3. Check the repository name and all links before submitting the repository URL through the official HackerFab form.
4. Be ready to explain the assumptions, limitations and validation plan in your own words.
