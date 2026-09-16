"""The colour of the sky, as a curve through the day.

A continuous function of the sun's elevation rather than a handful of labelled
buckets, so dusk arrives by sliding into it. Each key below is the look of the
sky at one sun elevation; the live value is interpolated between the two keys
either side of it.

    bri      how much of the bulb's brightness survives
    kelvin   warm or cool shift, for effects that set a colour temperature
    hue      the hue the weather's own colour gets dragged towards
    blend    how far it gets dragged
    rgb      the colour shown on the panel
    veil     how strongly that colour is laid over the panel lamp
"""

from __future__ import annotations

SKY_KEYS = [
    # elev    name              bri   kelvin  hue  blend  rgb                  veil
    (-90.0, "Deep night",      0.26,  -250,  235,  0.42, (0x08, 0x0E, 0x2A), 0.58),
    (-15.0, "Night",           0.28,  -300,  234,  0.42, (0x0B, 0x12, 0x33), 0.56),
    (-10.0, "Astronomical",    0.34,  -400,  231,  0.40, (0x14, 0x1E, 0x50), 0.54),
    (-6.0,  "Nautical",        0.44,  -750,  226,  0.42, (0x24, 0x32, 0x7E), 0.52),
    (-3.0,  "Civil twilight",  0.56, -1150,  268,  0.46, (0x4E, 0x3A, 0x8E), 0.50),
    (-0.8,  "At the horizon",  0.66, -1500,   10,  0.55, (0xD9, 0x52, 0x3E), 0.48),
    (2.0,   "Golden hour",     0.78, -1250,   28,  0.44, (0xEE, 0x8A, 0x3A), 0.40),
    (6.0,   "Low sun",         0.90,  -700,   42,  0.22, (0xF6, 0xC4, 0x7E), 0.26),
    # without this waypoint the gold interpolates straight into pale blue and
    # passes through a dead grey-green on the way
    (9.0,   "Low sun",         0.94,  -450,   45,  0.14, (0xE6, 0xD3, 0xBE), 0.18),
    (12.0,  "Climbing",        0.97,  -250,   48,  0.08, (0xB9, 0xD6, 0xEE), 0.10),
    (25.0,  "Daylight",        1.00,     0,   48,  0.00, (0x9C, 0xC8, 0xF2), 0.00),
    (90.0,  "High sun",        1.00,   200,   48,  0.00, (0x74, 0xB2, 0xEF), 0.00),
]

OVERCAST_RGB = (0x8A, 0x96, 0xA4)

# below this elevation the effects treat it as night
NIGHT_BELOW = -6.0


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_hue(a: float, b: float, t: float) -> float:
    """Go round the short way, so 268 -> 10 crosses magenta, not the whole wheel."""
    d = ((b - a + 180) % 360) - 180
    return (a + d * t) % 360


class Sky:
    """The tint of the hour, laid over whatever the weather is doing."""

    __slots__ = ("name", "bri_scale", "kelvin_bias", "hue_target",
                 "hue_blend", "rgb", "veil", "elevation")

    def __init__(self, name, bri_scale, kelvin_bias, hue_target, hue_blend,
                 rgb, veil, elevation):
        self.name = name
        self.bri_scale = bri_scale
        self.kelvin_bias = kelvin_bias
        self.hue_target = hue_target
        self.hue_blend = hue_blend
        self.rgb = rgb
        self.veil = veil
        self.elevation = elevation

    @property
    def night(self) -> bool:
        return self.elevation < NIGHT_BELOW

    @property
    def hex(self) -> str:
        return "#%02X%02X%02X" % tuple(int(max(0, min(255, c))) for c in self.rgb)

    def __repr__(self) -> str:
        return f"<Sky {self.name} at {self.elevation:+.1f} deg {self.hex}>"


def sky_at(elevation: float, cloud: float = 0.0) -> Sky:
    """The sky, for a sun this high and this much cloud (0-100)."""
    elevation = max(-90.0, min(90.0, elevation))
    lo = hi = SKY_KEYS[0]
    for a, b in zip(SKY_KEYS, SKY_KEYS[1:]):
        if a[0] <= elevation <= b[0]:
            lo, hi = a, b
            break

    span = hi[0] - lo[0]
    t = smoothstep((elevation - lo[0]) / span) if span else 0.0

    rgb = tuple(lerp(lo[6][i], hi[6][i], t) for i in range(3))

    # Cloud washes the colour out towards flat grey and takes the edge off the
    # brightness. Never all the way: even a downpour has a hue to it.
    murk = max(0.0, min(1.0, cloud / 100.0)) * 0.75
    rgb = tuple(lerp(rgb[i], OVERCAST_RGB[i], murk) for i in range(3))

    return Sky(
        name=lo[1] if t < 0.5 else hi[1],
        bri_scale=lerp(lo[2], hi[2], t) * (1 - 0.12 * murk),
        kelvin_bias=lerp(lo[3], hi[3], t),
        hue_target=lerp_hue(lo[4], hi[4], t),
        hue_blend=lerp(lo[5], hi[5], t),
        rgb=rgb,
        veil=lerp(lo[7], hi[7], t),
        elevation=elevation,
    )
