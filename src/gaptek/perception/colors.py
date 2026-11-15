"""rgb -> everyday Indonesian color name."""

import colorsys

_HUES = [  # (upper bound in degrees, name)
    (15, "merah"),
    (40, "oranye"),
    (65, "kuning"),
    (170, "hijau"),
    (200, "biru muda"),
    (250, "biru"),
    (290, "ungu"),
    (345, "merah muda"),
    (361, "merah"),
]


def color_name(rgb: tuple[int, int, int]) -> str:
    r, g, b = (c / 255 for c in rgb)
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    if lightness > 0.92:
        return "putih"
    if lightness < 0.12:
        return "hitam"
    if s < 0.18:
        return "abu-abu"
    deg = h * 360
    if 15 <= deg < 45 and lightness < 0.4:
        return "cokelat"
    return next(name for bound, name in _HUES if deg < bound)
