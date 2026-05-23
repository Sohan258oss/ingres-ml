from dataclasses import dataclass


CATEGORY_COLORS = {
    "Safe": "#2ecc71",
    "Semi-Critical": "#f39c12",
    "Critical": "#e67e22",
    "Over-Exploited": "#e74c3c",
}


@dataclass(frozen=True)
class AquiferProfile:
    name: str
    demand_growth: float
    recharge_response: float
    stress_memory: float
    uncertainty: float


ALLUVIAL_STATES = {
    "punjab", "haryana", "uttar pradesh", "bihar", "west bengal", "assam"
}

COASTAL_STATES = {
    "gujarat", "tamil nadu", "odisha", "andhra pradesh", "kerala", "goa", "west bengal"
}

HARD_ROCK_STATES = {
    "karnataka", "maharashtra", "telangana", "rajasthan", "madhya pradesh",
    "chhattisgarh", "jharkhand", "tamil nadu", "andhra pradesh"
}


AQUIFER_PROFILES = {
    "alluvial": AquiferProfile(
        name="Alluvial irrigation belt",
        demand_growth=0.018,
        recharge_response=0.84,
        stress_memory=0.28,
        uncertainty=0.08,
    ),
    "hard_rock": AquiferProfile(
        name="Hard-rock fractured aquifer",
        demand_growth=0.014,
        recharge_response=0.52,
        stress_memory=0.43,
        uncertainty=0.12,
    ),
    "coastal": AquiferProfile(
        name="Coastal salinity-sensitive aquifer",
        demand_growth=0.015,
        recharge_response=0.64,
        stress_memory=0.36,
        uncertainty=0.11,
    ),
    "mixed": AquiferProfile(
        name="Mixed aquifer system",
        demand_growth=0.013,
        recharge_response=0.68,
        stress_memory=0.34,
        uncertainty=0.1,
    ),
}


RAINFALL_FACTORS = {
    "dry": 0.86,
    "normal": 1.0,
    "wet": 1.12,
}


def classify_extraction(value):
    if value < 70:
        return "Safe"
    if value < 90:
        return "Semi-Critical"
    if value < 100:
        return "Critical"
    return "Over-Exploited"


def infer_aquifer_profile(state):
    state_key = (state or "").lower().strip()
    if state_key in COASTAL_STATES:
        return AQUIFER_PROFILES["coastal"]
    if state_key in HARD_ROCK_STATES:
        return AQUIFER_PROFILES["hard_rock"]
    if state_key in ALLUVIAL_STATES:
        return AQUIFER_PROFILES["alluvial"]
    return AQUIFER_PROFILES["mixed"]


def clamp(value, low, high):
    return max(low, min(high, value))


def normalize_pct(value):
    return clamp(float(value or 0), 0, 100) / 100


def simulate_groundwater_digital_twin(
    *,
    state,
    baseline_extraction,
    start_year,
    horizon_years,
    rainfall_scenario,
    crop_shift_pct,
    recharge_structures_pct,
    pumping_reduction_pct,
    urban_permeability_pct,
):
    profile = infer_aquifer_profile(state)
    rainfall_factor = RAINFALL_FACTORS.get((rainfall_scenario or "normal").lower(), 1.0)
    horizon_years = int(clamp(horizon_years or 6, 3, 15))
    start_year = int(start_year or 2024)
    baseline_extraction = clamp(float(baseline_extraction or 75), 5, 260)

    crop_shift = normalize_pct(crop_shift_pct)
    recharge_structures = normalize_pct(recharge_structures_pct)
    pumping_reduction = normalize_pct(pumping_reduction_pct)
    urban_permeability = normalize_pct(urban_permeability_pct)

    demand_cut = clamp(
        crop_shift * 0.34 + pumping_reduction * 0.72 + urban_permeability * 0.12,
        0,
        0.72,
    )
    recharge_gain = clamp(
        recharge_structures * 0.38 * profile.recharge_response
        + urban_permeability * 0.14 * profile.recharge_response,
        0,
        0.34,
    )
    rainfall_relief = (rainfall_factor - 1.0) * profile.recharge_response * 0.42
    stress_penalty = max(0, (baseline_extraction - 90) / 100) * profile.stress_memory * 0.025

    baseline_series = []
    intervention_series = []
    previous_baseline = baseline_extraction
    previous_intervention = baseline_extraction

    for offset in range(horizon_years + 1):
        year = start_year + offset
        if offset == 0:
            baseline_value = baseline_extraction
            intervention_value = baseline_extraction
        else:
            baseline_multiplier = 1 + profile.demand_growth + stress_penalty - rainfall_relief
            baseline_value = previous_baseline * baseline_multiplier

            ramp = offset / horizon_years
            target_intervention = baseline_value * (1 - demand_cut * ramp) / (1 + recharge_gain * ramp)
            inertia = profile.stress_memory * (1 - ramp * 0.35)

            # Aquifer stress has inertia; interventions do not erase overuse immediately.
            intervention_value = (
                target_intervention * (1 - inertia)
                + previous_intervention * inertia
            )

        baseline_value = round(clamp(baseline_value, 5, 280), 2)
        intervention_value = round(clamp(intervention_value, 5, 280), 2)
        band = max(3.0, intervention_value * profile.uncertainty)

        baseline_series.append({
            "year": year,
            "extraction": baseline_value,
            "category": classify_extraction(baseline_value),
        })
        intervention_series.append({
            "year": year,
            "extraction": intervention_value,
            "low": round(clamp(intervention_value - band, 5, 280), 2),
            "high": round(clamp(intervention_value + band, 5, 280), 2),
            "category": classify_extraction(intervention_value),
        })
        previous_baseline = baseline_value
        previous_intervention = intervention_value

    baseline_final = baseline_series[-1]["extraction"]
    intervention_final = intervention_series[-1]["extraction"]
    avoided_extraction = round(max(0, baseline_final - intervention_final), 2)

    def first_crossing(series, threshold):
        for point in series:
            if point["extraction"] >= threshold:
                return point["year"]
        return None

    def first_recovery(series, threshold):
        for point in series[1:]:
            if point["extraction"] < threshold:
                return point["year"]
        return None

    recharge_priority = "high" if profile.recharge_response >= 0.7 else "medium"
    if profile.name.startswith("Hard-rock"):
        primary_lever = "distributed recharge, borewell spacing, and demand restraint"
    elif profile.name.startswith("Coastal"):
        primary_lever = "coastal pumping caps and freshwater recharge barriers"
    else:
        primary_lever = "crop-water budgeting and irrigation demand reduction"

    return {
        "state": state,
        "aquifer_profile": profile.name,
        "rainfall_scenario": rainfall_scenario,
        "baseline_extraction": round(baseline_extraction, 2),
        "baseline_series": baseline_series,
        "intervention_series": intervention_series,
        "impact": {
            "avoided_extraction_pct_points": avoided_extraction,
            "relative_reduction_pct": round((avoided_extraction / baseline_final) * 100, 1) if baseline_final else 0,
            "baseline_final_category": classify_extraction(baseline_final),
            "intervention_final_category": classify_extraction(intervention_final),
            "baseline_tipping_year": first_crossing(baseline_series, 100),
            "intervention_tipping_year": first_crossing(intervention_series, 100),
            "intervention_recovery_year": first_recovery(intervention_series, 100),
        },
        "policy_levers": [
            {
                "name": "Demand reduction",
                "score": round(demand_cut * 100, 1),
                "interpretation": "Lower extraction pressure from crop shift and pumping restraint.",
            },
            {
                "name": "Recharge lift",
                "score": round(recharge_gain * 100, 1),
                "interpretation": f"Recharge response is {recharge_priority} for this aquifer profile.",
            },
            {
                "name": "System inertia",
                "score": round(profile.stress_memory * 100, 1),
                "interpretation": "Higher inertia means benefits arrive slowly even after intervention.",
            },
        ],
        "recommendation": (
            f"Prioritize {primary_lever}. The scenario avoids {avoided_extraction} percentage "
            f"points of extraction pressure by {start_year + horizon_years}."
        ),
        "method": "Deterministic hydro-balance digital twin v1; use as planning intelligence, not a field-validated hydrology model.",
        "color": CATEGORY_COLORS[classify_extraction(intervention_final)],
    }
