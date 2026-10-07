"""Free weather API integration — a live tool the AI chatbot can call.

Uses `Open-Meteo <https://open-meteo.com>`_, which is free for non-commercial
use and needs **no API key** — perfect for testing the chatbot end to end
without any paid credentials. Two public endpoints are used:

* Geocoding  — turn a city name into latitude/longitude.
* Forecast   — read the current conditions at those coordinates.

Everything is defensive: any network/parse problem returns ``None`` so the
caller can degrade gracefully, exactly like the other AI helpers.
"""

from __future__ import annotations

import re

import httpx

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo lists several Indian cities only under their official (renamed)
# spelling, so a common English name can resolve to the wrong place (e.g.
# "Bangalore" matches a small town in Pakistan). Map the popular aliases —
# and a frequent misspelling — to the name the geocoder actually indexes.
_CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "banglore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "madras": "Chennai",
    "poona": "Pune",
    "mysore": "Mysuru",
    "gurgaon": "Gurugram",
}

# WMO weather interpretation codes -> short human text.
# https://open-meteo.com/en/docs#weathervariables
_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

# Words that signal the shopper is asking about the weather. Matched on word
# boundaries so "hot" fires for "is it hot?" but not inside "shot" or "photo".
_WEATHER_HINTS = (
    "weather", "temperature", "temp", "forecast", "climate", "degrees",
    "celsius", "fahrenheit", "rain", "raining", "rainy", "snow", "snowing",
    "sunny", "cloudy", "windy", "wind", "humid", "humidity", "hot", "cold",
)
_WEATHER_RE = re.compile(r"\b(" + "|".join(_WEATHER_HINTS) + r")\b", re.IGNORECASE)


def is_weather_query(message: str) -> bool:
    """True when ``message`` looks like a weather question."""
    return bool(_WEATHER_RE.search(message))


def extract_city(message: str) -> str | None:
    """Pull a city name out of a weather question, e.g. "weather in Paris" -> "Paris".

    Falls back to ``None`` when no location is mentioned so the caller can ask
    the user to name a city.
    """
    # Match "... in/at/for <City Name>" up to end / punctuation.
    match = re.search(r"\b(?:in|at|for|of)\s+([A-Za-z][A-Za-z .'-]+)", message)
    if not match:
        return None
    city = match.group(1).strip(" .")
    # Drop trailing filler like "today", "right now", "please".
    city = re.sub(r"\b(today|now|right now|please|tomorrow|currently)\b.*$", "", city, flags=re.I)
    city = city.strip(" .,")
    return city or None


def _geocode(city: str) -> dict | None:
    """Resolve a city name to coordinates + display name via Open-Meteo.

    Open-Meteo returns candidates by name match, so a query like "Bangalore"
    can surface a tiny "Bangalore Town, Pakistan" ahead of the real city. We
    ask for several candidates and prefer the most populous one, which reliably
    picks the city the user actually means.
    """
    city = _CITY_ALIASES.get(city.strip().lower(), city)
    try:
        response = httpx.get(
            _GEOCODE_URL,
            params={"name": city, "count": 5, "language": "en", "format": "json"},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    results = (response.json() or {}).get("results") or []
    if not results:
        return None
    return max(results, key=lambda r: r.get("population") or 0)


def get_weather(city: str) -> str | None:
    """Return a one-line, human-readable current weather summary for ``city``.

    Returns ``None`` on any failure (unknown city, API/network error) so the
    chatbot can fall back to a friendly message.
    """
    place = _geocode(city)
    if not place:
        return None

    try:
        response = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            },
            timeout=15,
        )
        response.raise_for_status()
    except (httpx.HTTPError, KeyError):
        return None

    current = (response.json() or {}).get("current") or {}
    if "temperature_2m" not in current:
        return None

    name = place.get("name", city)
    country = place.get("country")
    where = f"{name}, {country}" if country else name
    condition = _WEATHER_CODES.get(current.get("weather_code"), "unknown conditions")
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")

    return (
        f"Current weather in {where}: {condition}, {temp}°C, "
        f"humidity {humidity}%, wind {wind} km/h."
    )


def weather_answer(message: str) -> str | None:
    """End-to-end helper for the chatbot: detect intent, fetch, format a reply.

    * Returns ``None`` when the message is not a weather question (so the bot
      can handle it normally).
    * Returns a ready-to-send string otherwise — either the live conditions,
      a prompt for a city, or a graceful failure message.
    """
    if not is_weather_query(message):
        return None
    city = extract_city(message)
    if not city:
        return "Which city's weather would you like? For example: “What's the weather in London?”"
    summary = get_weather(city)
    if not summary:
        return f"Sorry, I couldn't find the current weather for “{city}”. Please check the city name."
    return summary
