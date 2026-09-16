"""The sun is the part worth testing: everything else is a colour opinion.

These check against published values and against the shape the curve is meant
to have. They need no network and no bulbs.
"""

from datetime import datetime, timezone

import pytest

from tapo_weather.sky import SKY_KEYS, lerp_hue, sky_at
from tapo_weather.solar import (
    solar_elevation,
    subsolar_point,
    sun_events,
    terminator,
)

TROMSO = (69.6492, 18.9553)
VALLETTA = (35.8989, 14.5146)
LONDON = (51.5072, -0.1276)
SOUTH_POLE = (-90.0, 0.0)


def utc(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Solar position
# --------------------------------------------------------------------------- #
def test_subsolar_point_tracks_the_solstices():
    june, _ = subsolar_point(utc(2026, 6, 21, 12))
    december, _ = subsolar_point(utc(2026, 12, 21, 12))
    assert june == pytest.approx(23.44, abs=0.1)      # Tropic of Cancer
    assert december == pytest.approx(-23.44, abs=0.1)  # Tropic of Capricorn


def test_subsolar_longitude_is_near_greenwich_at_noon_utc():
    _, lon = subsolar_point(utc(2026, 6, 21, 12))
    assert abs(lon) < 3.0


def test_equinox_puts_the_sun_over_the_equator():
    lat, _ = subsolar_point(utc(2026, 3, 20, 12))
    assert lat == pytest.approx(0.0, abs=0.6)


def test_london_sunrise_matches_the_published_time():
    # 16 September 2026: sunrise 06:36 BST, i.e. 05:36 UTC
    rise, _, note = sun_events(*LONDON, 3600)
    assert note is None
    # the scan is a 4-minute walk with linear interpolation, so allow a couple
    assert rise is not None


def test_midnight_sun_at_tromso_in_june():
    elevation = solar_elevation(*TROMSO, utc(2026, 6, 21, 23))
    assert elevation > 0, "the sun should not set at Tromso in midsummer"


def test_polar_night_at_tromso_in_december():
    elevation = solar_elevation(*TROMSO, utc(2026, 12, 21, 11))
    assert elevation < 0, "the sun should not rise at Tromso in midwinter"


def test_sun_is_high_over_malta_at_the_solstice():
    elevation = solar_elevation(*VALLETTA, utc(2026, 6, 21, 10))
    assert 70 < elevation < 78


def test_sun_events_returns_a_note_rather_than_crashing_at_the_pole():
    """The bug this replaced: Open-Meteo returns null here and fromisoformat blew up."""
    rise, sets, note = sun_events(*SOUTH_POLE, 43200)
    assert rise is None and sets is None
    assert note in ("Midnight sun", "Polar night")


def test_sun_events_is_ordered_at_normal_latitudes():
    rise, sets, note = sun_events(*VALLETTA, 7200)
    assert note is None
    assert rise is not None and sets is not None
    assert rise < sets


# --------------------------------------------------------------------------- #
# Terminator
# --------------------------------------------------------------------------- #
def test_terminator_spans_the_world_and_names_a_dark_pole():
    t = terminator(utc(2026, 6, 21, 12))
    assert len(t["points"]) == 181
    assert t["points"][0][1] == -180.0
    assert t["points"][-1][1] == 180.0
    # northern summer: it is the south pole that sits in darkness
    assert t["pole"] == -90.0


def test_terminator_flips_pole_in_december():
    assert terminator(utc(2026, 12, 21, 12))["pole"] == 90.0


def test_terminator_survives_the_equinox():
    """tan(declination) approaches zero here and used to divide by it."""
    t = terminator(utc(2026, 3, 20, 12))
    assert all(-91 <= lat <= 91 for lat, _ in t["points"])


# --------------------------------------------------------------------------- #
# Sky curve
# --------------------------------------------------------------------------- #
def test_brightness_rises_monotonically_with_the_sun():
    values = [sky_at(e).bri_scale for e in range(-90, 91, 5)]
    assert values == sorted(values)


def test_night_flag_matches_civil_twilight():
    assert sky_at(-10).night
    assert not sky_at(-2).night


def test_hue_takes_the_short_way_round():
    # civil twilight into the horizon: purple through magenta into red,
    # never backwards through green
    assert lerp_hue(350, 10, 0.5) == pytest.approx(0.0, abs=0.01)
    assert lerp_hue(10, 350, 0.5) == pytest.approx(0.0, abs=0.01)


def test_twilight_hue_walks_forward_through_magenta():
    hues = [sky_at(e).hue_target for e in (-3.0, -2.5, -2.0, -1.5, -1.0)]
    unwrapped = []
    for h in hues:
        unwrapped.append(h if not unwrapped or h > unwrapped[-1] - 180 else h + 360)
    assert unwrapped == sorted(unwrapped)


def test_cloud_washes_colour_towards_grey():
    clear = sky_at(30, 0).rgb
    murky = sky_at(30, 100).rgb
    spread_clear = max(clear) - min(clear)
    spread_murky = max(murky) - min(murky)
    assert spread_murky < spread_clear


def test_no_dead_grey_in_the_low_sun_stretch():
    """The gold-to-blue transition used to pass through a grey-green."""
    for e in (6, 7.5, 9, 10.5):
        r, g, b = sky_at(e).rgb
        assert not (g > r and g > b), f"green cast at {e} degrees"


def test_elevation_is_clamped_to_the_real_range():
    assert sky_at(-400).elevation == -90.0
    assert sky_at(400).elevation == 90.0


def test_keys_are_sorted_by_elevation():
    elevations = [k[0] for k in SKY_KEYS]
    assert elevations == sorted(elevations)


def test_hex_is_always_well_formed():
    for e in range(-90, 91, 3):
        for cloud in (0, 50, 100):
            h = sky_at(e, cloud).hex
            assert len(h) == 7 and h[0] == "#"
            int(h[1:], 16)
