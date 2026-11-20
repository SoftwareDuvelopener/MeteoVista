"""Refresh the local Zolder forecast: py generate_forecast.py.

Requires Python 3.8+ and Windows curl.exe. Open forecast.html in your browser.
Keep the icons directory next to forecast.html for offline viewing.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree


SOURCE = "https://www.meteovista.be/Europa/Belgie/Zolder/4055754/weersverwachting-14dagen"
ICONS = "https://assets.infoplaza.io/site/assets/icons"
ROOT = Path(__file__).resolve().parent
DAYS = "Maandag Dinsdag Woensdag Donderdag Vrijdag Zaterdag Zondag".split()
MONTHS = "jan feb mrt apr mei jun jul aug sep okt nov dec".split()
DIRECTIONS = "N NNO NO ONO O OZO ZO ZZO Z ZZW ZW WZW W WNW NW NNW".split()


def fetch(url):
    result = subprocess.run(
        ["curl.exe", "--fail", "--silent", "--show-error", "--location",
         "--proto", "=https", "--max-time", "20", url],
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise OSError(f"{url}: {detail or f'curl exited with code {result.returncode}'}")
    return result.stdout


def forecast_days():
    page = fetch(SOURCE).decode("utf-8")
    data = re.search(r'<script\b[^>]*\bid="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not data:
        raise ValueError("Meteovista did not return its embedded forecast data.")
    days = json.loads(data[1])["props"]["pageProps"]["forecastDay"]
    if not isinstance(days, list) or len(days) < 5:
        raise ValueError("Meteovista did not return five daily forecasts.")
    return days[:5]


def save_icon(category, filename):
    path = ROOT / "icons" / filename
    if not path.is_file():
        svg = fetch(f"{ICONS}/{category}/{filename}")
        if ElementTree.fromstring(svg).tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError(f"{filename} is not an SVG.")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(svg)
    return f"icons/{filename}"


def rain_label(amount):
    # Meteovista displays tenths below 1 mm and whole millimetres above that.
    precision = "0.1" if amount < 1 else "1"
    rounded = Decimal(str(amount)).quantize(Decimal(precision), rounding=ROUND_HALF_UP)
    return format(rounded.normalize(), "f").replace(".", ",") + " mm"


def render_row(day):
    date = datetime.fromisoformat(day["intervalStart"]["formatted"]).date()
    temperatures = day["temperature"]
    low, high = (int(temperatures[key]) for key in ("min", "max"))
    rain = day["precipitation"]["amount"]
    rain_class = "wet" if rain > 0 else "dry"
    wind = day["wind"]
    direction = wind["direction"]
    rotation = DIRECTIONS.index(direction) * 22.5
    beaufort = int(wind["speed"]["bft"])
    score = int(day["digits"]["weather"])
    code = day["weatherSymbol"]["code"].lower()
    if not re.fullmatch(r"[a-z0-9]+", code):
        raise ValueError(f"Unexpected weather icon code: {code!r}")
    weather_icon = save_icon("weather/v2", f"{code}.svg")
    score_icon = save_icon("activities/v1", f"grade_{score}_light.svg")

    return f"""      <tr>
        <th scope="row">{DAYS[date.weekday()]}
          <time datetime="{date.isoformat()}">{date.day} {MONTHS[date.month - 1]}</time>
        </th>
        <td><img class="weather" src="{weather_icon}" alt="Weersymbool"></td>
        <td class="temperature">{low}&deg; / {high}&deg;</td>
        <td class="{rain_class}">{rain_label(rain)}</td>
        <td><span class="wind" role="img" aria-label="Wind uit {direction}, {beaufort} beaufort"
                  title="{direction}, {beaufort} Bft">
          <svg viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
            <path d="M9 5 L16 7 L23 5 L16 30 Z" transform="rotate({rotation} 16 16)"
                  fill="currentColor" stroke="currentColor" stroke-linejoin="round"/>
            <circle cx="16" cy="16" r="8" fill="white" stroke="currentColor" stroke-width="2"/>
          </svg>
          <span aria-hidden="true">{beaufort}</span>
        </span></td>
        <td><img class="score" src="{score_icon}" alt="{score} op 10"></td>
      </tr>"""


def render_page(rows):
    return """<!doctype html>
<html lang="nl-BE">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>5-daagse weersverwachting voor Zolder</title>
  <style>
    body { margin: 0 0 0 8px; background: #fff; color: #071d3c;
           font: 15px "Century Gothic", "Segoe UI", sans-serif; }
    main { max-width: 645px; }
    h1 { margin: 0; font-size: 26px; line-height: 1.15; }
    .subtitle { margin: 14px 0 26px; color: #68768b; font-size: 17px; }
    table { width: 100%; table-layout: fixed; border-collapse: collapse; }
    .weather-col { width: 56px; } .temp-col { width: 110px; }
    .rain-col { width: 78px; } .wind-col { width: 58px; } .score-col { width: 46px; }
    th, td { padding: 0; }
    thead th { height: 26px; color: #626c78; font-weight: 400; }
    tr { border-bottom: 1px solid #e1e4e9; }
    tbody th { text-align: left; font-weight: 500; }
    time { display: block; margin-top: 4px; color: #627186; }
    td { height: 75px; text-align: center; white-space: nowrap; font-size: 20px; }
    .wet { color: #007df0; } .dry { color: #68717b; }
    img { display: block; margin: auto; }
    .weather { width: 50px; height: 40px; }
    .score { width: 32px; height: 32px; }
    .wind { display: grid; width: 32px; height: 32px; margin: auto;
            place-items: center; color: #406397; font-size: 11.5px; font-weight: 700; line-height: 1; }
    .wind > * { grid-area: 1 / 1; }
    footer { margin: 14px 0; font-size: 13px; color: #68768b; }
    footer a { color: inherit; }
    @media (max-width: 460px) {
      h1 { font-size: 23px; }
      .weather-col { width: 44px; } .temp-col { width: 68px; }
      .rain-col { width: 60px; } .wind-col { width: 43px; } .score-col { width: 38px; }
      td { font-size: 15px; }
      thead th, tbody th { font-size: 13px; }
      .weather { width: 40px; height: 32px; }
    }
  </style>
</head>
<body>
<main>
  <h1>5-daagse weersverwachting</h1>
  <p class="subtitle">Het weer komende 5 dagen in Zolder.</p>
  <table aria-label="Weersverwachting voor Zolder">
    <colgroup><col><col class="weather-col"><col class="temp-col">
      <col class="rain-col"><col class="wind-col"><col class="score-col"></colgroup>
    <thead>
      <tr><th scope="col" aria-label="Dag"></th><th scope="col">weer</th>
        <th scope="col">min/max</th><th scope="col">neerslag</th>
        <th scope="col">wind</th><th scope="col">cijfer</th></tr>
    </thead>
    <tbody>
""" + "\n".join(rows) + f"""
    </tbody>
  </table>
  <footer>Bron: <a href="{SOURCE}">Meteovista</a></footer>
</main>
</body>
</html>
"""


def main():
    output = ROOT / "forecast.html"
    try:
        html = render_page([render_row(day) for day in forecast_days()])
        output.write_text(html, encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError, ElementTree.ParseError) as error:
        print(f"Could not generate the forecast: {error}", file=sys.stderr)
        return 1
    print(f"Open in your browser: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
