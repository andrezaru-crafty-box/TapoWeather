# Weather lamp

Your Tapo bulbs, showing the weather and the hour of the day somewhere else in
the world. Pick a place from a map and the room fills with its light: rain
patters, thunderstorms strike, fog breathes, and everything is tinted by how
high the sun is standing over that particular patch of the planet right now.

Runs on your own machine. No API keys, no cloud service, no account beyond the
Tapo one you already have.

## What it does

The colour is built in two layers.

**The weather decides the character.** Rain gives each bulb its own droplet
rhythm so they never fall in step. Storms sit dark and then strike. Fog and
snow breathe at slightly detuned periods, so three bulbs drift apart instead of
pulsing as one.

**The sun decides the colour it is painted in.** A continuous curve runs from
deep night up through the blues of nautical twilight, the purples and magentas
of civil twilight, the red of a sun sitting on the horizon, gold, and into full
daylight. It is recomputed every few seconds, so dusk arrives by sliding into
it rather than snapping at a boundary.

The sun's position is calculated locally rather than read from a weather feed.
That matters above the Arctic circle, where sunrise and sunset are not events
that happen every day. Point it at Tromsø in December and it says "Polar
night"; point it at Svalbard in June and the light never goes fully dark.

## Running it

```bash
git clone https://github.com/YOUR-USERNAME/tapo-weather-lamp.git
cd tapo-weather-lamp
python -m pip install -r requirements.txt
python run.py
```

Then open <http://localhost:8765>, or the same port on this machine's LAN
address from your phone.

With nothing configured it runs in **preview mode**: the panel works, the
colours appear on screen, and no bulbs are touched. That is the right way to
try it before giving it your password.

### Connecting real bulbs

```bash
cp .env.example .env
```

Fill in your Tapo account email and the LAN addresses of your bulbs. You can
find those in your router's client list, or in the Tapo app under each device.

Leave `TAPO_PASSWORD` blank in the file and you will be asked for it when the
program starts, which keeps it off your disk entirely. That is the safer
option, and the one I would use.

If you would rather not type it every time, set it as a real environment
variable instead of putting it in the file:

```bash
# Windows, once, then open a new terminal
setx TAPO_PASSWORD "your-tapo-password"

# macOS or Linux, in your shell profile
export TAPO_PASSWORD="your-tapo-password"
```

Only L530 colour bulbs are wired up at the moment.

## Keeping your details private

This repository is written on the assumption that you might make it public.

- `.env` is gitignored and `.env.example` holds only placeholders. Your
  password and account email never enter source control.
- Bulb addresses come from `TAPO_IPS`, not from the code. They describe your
  home network, which is worth keeping to yourself.
- `Settings.__repr__` prints `password=<set>` and a count of addresses rather
  than the values, so a stray log line or a traceback cannot leak them.
- `presets.local.json` is gitignored. The shipped `presets.json` is a generic
  list; if you replace it with the towns you actually watch, use the local file
  so your habits stay off the internet.
- A test walks every source file and fails the build if an email address or a
  private IP range appears in it. This project had both hardcoded once.

**If you have already committed a password anywhere, change it in the Tapo app
first.** Deleting the line does not remove it from your git history, and
rewriting history is more work than rotating a password.

## Configuration

Every value is optional. Real environment variables take priority over `.env`.

| Variable | Default | What it does |
| --- | --- | --- |
| `TAPO_USERNAME` | unset | The email you sign in to Tapo with |
| `TAPO_PASSWORD` | unset | Blank prompts at startup, which is safer |
| `TAPO_IPS` | unset | Bulb addresses, comma separated |
| `LAMP_HOST` | `0.0.0.0` | `127.0.0.1` keeps the panel off your LAN |
| `LAMP_PORT` | `8765` | Port for the panel |
| `LAMP_REFRESH_SECONDS` | `600` | How often to re-fetch the weather |
| `LAMP_USER_AGENT` | project string | Sent to Nominatim, which asks you to identify yourself |

## Layout

```
tapo_weather/
  config.py     settings from the environment, and nowhere else
  solar.py      sun position, sunrise and sunset, the day/night terminator
  sky.py        the colour curve from deep night to high sun
  weather.py    Open-Meteo and Nominatim
  lights.py     bulb connection, command fan-out, shutdown
  effects.py    one function per kind of weather, and the shared state
  runner.py     the loop that ties them together
  server.py     the panel's endpoints
  web/          the panel itself
tests/          the sun, the curve, the endpoints, and the secret handling
```

The split matters in one place. Weather is re-fetched on a slow timer, but the
sun is recomputed every beat. Nothing waits for a network call to notice that
the light has changed.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

No network and no hardware required. The solar maths is checked against
published values: London's sunrise lands within a couple of minutes, and the
subsolar point sits on the Tropic of Cancer at the June solstice and the Tropic
of Capricorn in December.

## Data sources

- Weather: [Open-Meteo](https://open-meteo.com/), no key needed
- Search: Open-Meteo's geocoding API
- Map clicks: [Nominatim](https://nominatim.org/), whose
  [usage policy](https://operations.osmfoundation.org/policies/nominatim/) asks
  for an identifying user agent and no more than one request a second
- Tiles: OpenStreetMap via CARTO

## Licence

MIT. See [LICENSE](LICENSE).
