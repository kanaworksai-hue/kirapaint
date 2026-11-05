# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ten painted backdrops. What the camera sees changes; the colored reflections that make the sparkle stay."""

import math

# paint: five posterized paint colors (dark -> light), top / bottom: a vertical wash over the paint,
# wash: how much of the wash shows, dots: None / "POLKA" / "STARS", doodle: chalk color that reads on it
BACKGROUNDS = {
    "NIGHT": dict(label="Night Purple", ja="夜空パープル",
                  paint=["#0a0618", "#120c26", "#1a1340", "#251b5a", "#3a2c78"],
                  top="#2a1d5c", bottom="#0d0820", wash=0.25, dots=None, doodle="#f3ebe0"),
    "STARRY": dict(label="Starry Sky", ja="星空ネイビー",
                   paint=["#050818", "#0a1030", "#101a48", "#18255e", "#22347a"],
                   top="#0b1544", bottom="#1c1640", wash=0.45, dots="STARS", doodle="#fff4d6"),
    "SAKURA": dict(label="Sakura Pink", ja="さくらピンク",
                   paint=["#e98aa8", "#f2a3bb", "#f7b8cb", "#fbcbd8", "#ffdbe5"],
                   top="#ffe3ec", bottom="#f093b0", wash=0.35, dots=None, doodle="#7a3355"),
    "POLKA": dict(label="Strawberry Polka", ja="いちごミルク水玉",
                  paint=["#f6a5bd", "#f8b2c6", "#fabfd0", "#fccbd9", "#fdd6e1"],
                  top="#ffd9e4", bottom="#f4a0ba", wash=0.3, dots="POLKA", doodle="#8a2f55"),
    "MINT": dict(label="Mint Soda", ja="ミントソーダ",
                 paint=["#6fc9b3", "#86d6c2", "#9fe2d1", "#b7ecdf", "#cdf5eb"],
                 top="#d8faf1", bottom="#5fbca6", wash=0.35, dots=None, doodle="#1f5e57"),
    "SODA": dict(label="Sky Soda", ja="空色ソーダ",
                 paint=["#6aa8e8", "#80b8ef", "#98c8f4", "#b1d7f8", "#c9e5fb"],
                 top="#d6ecff", bottom="#5c95dc", wash=0.35, dots=None, doodle="#22457e"),
    "LEMON": dict(label="Lemon Cream", ja="レモンクリーム",
                  paint=["#f2d46b", "#f6de85", "#f9e79e", "#fbefb6", "#fdf5cc"],
                  top="#fff8d8", bottom="#efc95a", wash=0.35, dots=None, doodle="#7a5a12"),
    "PEACH": dict(label="Peach Dream", ja="ピーチドリーム",
                  paint=["#f2a48a", "#f5b39b", "#f8c3ad", "#fad2c0", "#fde0d3"],
                  top="#d9c6f5", bottom="#f59f86", wash=0.6, dots=None, doodle="#7a3b2e"),
    "SUNSET": dict(label="Magic Sunset", ja="マジックサンセット",
                   paint=["#3b1c5a", "#6a2a6e", "#a83f72", "#e2677a", "#f7a26c"],
                   top="#4a2373", bottom="#f59a5f", wash=0.75, dots="STARS", doodle="#fff1dc"),
    "STUDIO": dict(label="Soft Studio", ja="ソフトスタジオ",
                   paint=["#bfbac4", "#c9c4ce", "#d3cfd8", "#ddd9e1", "#e7e4ea"],
                   top="#eeebf1", bottom="#b4afba", wash=0.6, dots=None, doodle="#4b4458"),
}
ORDER = ("NIGHT", "STARRY", "SAKURA", "POLKA", "MINT", "SODA", "LEMON", "PEACH", "SUNSET", "STUDIO")


def hex_to_linear(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def hex_to_srgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def icon_pixels(key, size=96):
    """A small swatch for the panel: the vertical wash, a few paint blotches and the dots."""
    bg = BACKGROUNDS[key]
    paint = [hex_to_srgb(c) for c in bg["paint"]]
    top, bottom = hex_to_srgb(bg["top"]), hex_to_srgb(bg["bottom"])
    px = []
    for y in range(size):
        v = y / (size - 1)                      # 0 bottom .. 1 top (Blender image rows go bottom-up)
        for x in range(size):
            u = x / (size - 1)
            n = 0.5 + 0.25 * math.sin(u * 7.1 + v * 3.3) + 0.25 * math.sin(u * 2.3 - v * 8.7 + 1.3)
            idx = min(4, max(0, int(n * 5)))
            p = paint[idx]
            w = (bottom[0] + (top[0] - bottom[0]) * v, bottom[1] + (top[1] - bottom[1]) * v,
                 bottom[2] + (top[2] - bottom[2]) * v)
            c = [p[i] * (1 - bg["wash"]) + w[i] * bg["wash"] for i in range(3)]
            if bg["dots"] == "POLKA":
                gx, gy = (u * 4) % 1 - 0.5, (v * 4 + (0.5 if int(u * 4) % 2 else 0)) % 1 - 0.5
                if gx * gx + gy * gy < 0.045:
                    c = [1.0, 0.97, 0.98]
            elif bg["dots"] == "STARS":
                h = math.sin(x * 12.9898 + y * 78.233) * 43758.5453
                if h - math.floor(h) > 0.985:
                    c = [1.0, 0.97, 0.88]
            px.extend((*c, 1.0))
    return px
