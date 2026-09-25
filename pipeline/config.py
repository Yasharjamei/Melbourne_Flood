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
    # The two papers' study area. Built to dist/index.html.
    "west": {
        "title": "Maribyrnong and Moonee Valley",
        "label": "Both councils",
        "lgas": ["Maribyrnong", "Moonee Valley"],
        "out": "index.html",
        "simplify_m": 4,
        "mgwr": True,   # the paper's GWR/MGWR (Table 5, Fig. 4) on its own 474 SA1s
    },
    # All 31 Greater Melbourne councils. Built to dist/metro/index.html.
    "metro": {
        "title": "Greater Melbourne",
        "label": "All 31 councils",
        "lgas": GREATER_MELBOURNE,
        "out": "metro/index.html",
        "simplify_m": 12,
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
