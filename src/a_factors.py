"""Method constants for the inventory (values documented in the pack's docs/METHODOLOGY.md; same
numbers as the pack's MIT-licensed tools/ccn_tools/factors.py, © Since AI ry). Kept here so our
calculator never imports or executes pack code."""

GRID_FI_LB = {2019: 0.09, 2020: 0.068, 2021: 0.075, 2022: 0.066, 2023: 0.038, 2024: 0.03, 2025: 0.026}
RESIDUAL_FI = {2019: 0.354, 2020: 0.37, 2021: 0.38, 2022: 0.39, 2023: 0.4, 2024: 0.406, 2025: 0.406}
GRID_SE_LB = {y: 0.012 for y in range(2019, 2026)}
RESIDUAL_SE = {2019: 0.04, 2020: 0.045, 2021: 0.04, 2022: 0.04, 2023: 0.038, 2024: 0.036, 2025: 0.035}
HEAT_LB_EF = {2019: 0.16, 2020: 0.15, 2021: 0.15, 2022: 0.14, 2023: 0.13, 2024: 0.12, 2025: 0.11}

FUEL_EF_T_PER_MWH = {"natural_gas": 0.2009, "lng": 0.1991, "lpg": 0.2336, "light_fuel_oil": 0.2668,
                     "heavy_fuel_oil": 0.284, "diesel": 0.211, "milled_peat": 0.3874, "wood_chips": 0.0,
                     "wood_pellets": 0.0, "biogas": 0.0, "hvo": 0.0, "oilseed_sidestream": 0.0}
FUEL_BIOGENIC_T_PER_MWH = {"wood_chips": 0.4032, "wood_pellets": 0.4032, "biogas": 0.198, "hvo": 0.264,
                           "oilseed_sidestream": 0.45, "diesel": 0.035}
FUEL_WTT = {"lng": "EF-WTT-LNG", "lpg": "EF-WTT-LPG", "light_fuel_oil": "EF-WTT-LFO", "diesel": "EF-WTT-DIESEL",
            "natural_gas": "EF-WTT-NG", "wood_chips": "EF-WTT-WOOD", "oilseed_sidestream": "EF-WTT-WOOD",
            "biogas": "EF-WTT-BIOGAS", "hvo": "EF-WTT-HVO"}
NCV_MWH = {"lng": 13.5, "lpg": 12.8, "light_fuel_oil": 0.01, "diesel": 0.0099}  # per t (LNG/LPG) or per litre

REFRIGERANT_GWP = {"R717_ammonia": 0, "R744_co2": 1, "R404A": 4728, "R507A": 4775, "R449A": 1504,
                   "R410A": 2256, "R134a": 1530, "R32": 771}
FX_PER_EUR = {"EUR": 1.0, "SEK": 11.4, "USD": 1.08}

FARM_EF = {"ef1_synthetic": 0.016, "ef1_organic": 0.006, "frac_gasf": 0.05, "frac_gasm": 0.21, "frac_leach": 0.24,
           "ef4_n2o_n": 0.014, "ef5_n2o_n": 0.011, "n2o_gwp": 273, "n2o_n_to_n2o": 44 / 28,
           "fert_n_prod": 3.7, "fert_n_prod_lowcarbon": 0.9, "fert_p_prod": 1.6, "fert_k_prod": 0.5,
           "diesel_ttw": 2.1, "diesel_wtt": 0.61, "lime": 0.44, "org_soil_co2_t_ha": 29.0,
           "org_soil_co2_grass_t_ha": 20.9, "org_soil_n2o_n_kg_ha": 13.0, "spray_pass": 8.0}
KWH_PER_T = {"pea": 8, "potato": 35, "carrot": 30, "spinach": 6, "turnip_rape": 45}
RESIDUE_N_PER_T = {"pea": 6.0, "potato": 1.2, "carrot": 1.0, "spinach": 1.5, "turnip_rape": 18.0}
CROP_MATERIAL = {"M100": "turnip_rape", "M110": "pea", "M111": "potato", "M112": "carrot", "M113": "spinach"}

USE_PHASE_KWH_PER_KG = {"frozen_vegetables": 0.71, "ready_meals_frozen": 0.96, "fish_products": 0.96,
                        "frozen_pizza": 1.81, "rapeseed_oil_bottled": 0.0, "rapeseed_oil_bulk": 0.0,
                        "rapeseed_meal_expeller": 0.0, "blackgrain_powder": 0.0}
PACK_KG_PER_T = {"frozen_vegetables": (19.0, 32.0), "ready_meals_frozen": (24.0, 60.0), "fish_products": (22.0, 55.0),
                 "frozen_pizza": (14.0, 85.0), "rapeseed_oil_bottled": (52.0, 18.0), "rapeseed_oil_bulk": (0.6, 0.0),
                 "rapeseed_meal_expeller": (0.0, 0.0), "blackgrain_powder": (30.0, 20.0)}
EOL_PLASTIC_EF_T = 1.40485
EOL_BOARD_EF_T = 0.07935
MARKET_GRID = {"FI": GRID_FI_LB, "SE": GRID_SE_LB, "EXPORT_EU": {y: 0.230 for y in range(2015, 2031)}}

A2_WEIGHTS = {"scope1_total": 0.15, "scope2_location_total": 0.03, "scope2_market_total": 0.12, "scope3_total": 0.20,
              "cat01_purchased_goods_services": 0.20, "cat02_capital_goods": 0.03, "cat03_fuel_energy": 0.04,
              "cat04_upstream_transport": 0.08, "cat05_waste": 0.04, "cat06_business_travel": 0.02,
              "cat07_employee_commuting": 0.02, "cat09_downstream_transport": 0.04,
              "cat11_use_of_sold_products": 0.015, "cat12_end_of_life": 0.015}
