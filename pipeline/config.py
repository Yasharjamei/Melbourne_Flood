"""Study areas and shared settings. Run any pipeline step with --study <key>."""

# LGA names as ASGS 2021 publishes them, minus any " (Vic.)" suffix.
# Merri-bek is still "Moreland" in ASGS 2021; both spellings are accepted.
GREATER_MELBOURNE = [
    "Banyule", "Bayside", "Boroondara", "Brimbank", "Cardinia", "Casey", "Darebin",
    "Frankston", "Glen Eira", "Greater Dandenong", "Hobsons Bay", "Hume", "Kingston",
    "Knox", "Manningham", "Maribyrnong", "Maroondah", "Melbourne", "Melton", "Moreland",
    "Monash", "Moonee Valley", "Mornington Peninsula", "Nillumbik", "Port Phillip",
    "Stonnington", "Whitehorse", "Whittlesea", "Wyndham", "Yarra", "Yarra Ranges",
]

STUDIES = {
    # One page for all 31 Greater Melbourne councils, built to dist/index.html. The papers' own
    # study area (Maribyrnong + Moonee Valley, 474 SA1s) lives inside it as a preset filter and
    # as a second regression model, so the reproduction of Lama & Sun's Table 5 is kept.
    "metro": {
        "title": "Greater Melbourne",
        "label": "All 31 councils",
        "lgas": GREATER_MELBOURNE,
        "out": "index.html",
        "simplify_m": 12,
        "mgwr": "SA2",  # too many SA1s for MGWR (cost ~ n^2), so the metro model is fitted on ~300 SA2s
        "paper": {      # the paper's own units, fitted on SA1s like Lama & Sun
            "label": "Paper study area (Lama & Sun)",
            "lgas": ["Maribyrnong", "Moonee Valley"],
        },
    },
}

ALIASES = {"merri-bek": "moreland"}


def norm_lga(name):
    n = name.replace(" (Vic.)", "").strip().lower()
    return ALIASES.get(n, n)


# Lama & Sun (2026) Table 2 AHP weights. Direction +1: higher raw value raises the
# dimension score; -1: normalised value is flipped (1 - x) first.
LAMA_SUN = {
    "exposure": [("flood", 0.019, +1), ("elev", 0.014, -1), ("sand", 0.014, -1)],
    "sensitivity": [("urban", 0.050, +1), ("dwell", 0.050, +1), ("pop", 0.074, +1),
                    ("dep", 0.074, +1), ("ltc", 0.110, +1)],
    "adaptive": [("emp", 0.168, +1), ("edu", 0.168, +1), ("incgen", 0.259, +1)],
}
DAMAGE_INDICATORS = ["urban", "dwell", "pop", "dep", "ltc", "emp", "edu", "incgen"]
