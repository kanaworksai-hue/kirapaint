# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Looks. Every value here is also a slider in the panel."""

# stroke      how strongly the surface is broken into painted facets (normal distortion), 0-1
# facets      facet density, 1 = about 6.5 facets across the object
# gloss       how glossy the facets get (pulls roughness toward 0.06), 0-1
# iridescence pink / cyan thin-film sheen on the facets, 0-1
# brush       brush size in pixels at 1080p (scaled to the render resolution)
# sparkle     four-point star glints and the glint lights, 0-1
# bloom       soft glow, 0-1
# outline     outline width multiplier (0 = no outline)
PRESETS = {
    "KIRA": {
        "label": "Kira (crushed diamond)",
        "description": "Glossy painted facets with colored glints and star sparkles",
        "stroke": 0.72, "facets": 1.0, "gloss": 0.85, "iridescence": 0.7,
        "brush": 4.0, "sparkle": 0.75, "bloom": 0.48, "outline": 1.0,
    },
    "SOFT": {
        "label": "Soft Paint",
        "description": "Gentle oil-paint strokes, few sparkles",
        "stroke": 0.5, "facets": 0.8, "gloss": 0.35, "iridescence": 0.15,
        "brush": 6.0, "sparkle": 0.15, "bloom": 0.4, "outline": 0.8,
    },
    "INK": {
        "label": "Bold Ink",
        "description": "Thick outline, crisp strokes, a little shine",
        "stroke": 0.62, "facets": 1.2, "gloss": 0.6, "iridescence": 0.3,
        "brush": 4.0, "sparkle": 0.4, "bloom": 0.3, "outline": 2.0,
    },
    "DREAMY": {
        "label": "Dreamy",
        "description": "Strong rainbow sheen, lots of glow and sparkles",
        "stroke": 0.8, "facets": 1.0, "gloss": 0.9, "iridescence": 1.0,
        "brush": 5.0, "sparkle": 1.0, "bloom": 0.7, "outline": 0.7,
    },
}
ORDER = ("KIRA", "SOFT", "INK", "DREAMY")
LOOK_KEYS = ("stroke", "facets", "gloss", "iridescence", "brush", "sparkle", "bloom", "outline")
