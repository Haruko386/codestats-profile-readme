#!/usr/bin/env python3
"""Fetch one Code::Stats day and render a GitHub-coloured history SVG."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "history-graph.json"
LINGUIST_URL = (
    "https://raw.githubusercontent.com/github-linguist/linguist/"
    "main/lib/linguist/languages.yml"
)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


class GeneratorError(RuntimeError):
    """A user-facing generation error."""


def http_text(url: str, *, data: bytes | None = None) -> str:
    request = Request(
        url,
        data=data,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "text/plain; charset=utf-8",
            "User-Agent": "codestats-history-graph/1.0",
        },
        method="POST" if data is not None else "GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise GeneratorError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except URLError as exc:
        raise GeneratorError(f"Could not reach {url}: {exc.reason}") from exc


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GeneratorError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GeneratorError(f"Invalid JSON in {path}: {exc}") from exc


def validate_config(config: dict[str, Any]) -> None:
    required = {
        "username",
        "timezone",
        "history_days",
        "max_languages",
        "width",
        "height",
        "show_legend",
        "output",
        "history_file",
        "colors_file",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise GeneratorError(f"Missing config keys: {', '.join(missing)}")
    if not str(config["username"]).strip():
        raise GeneratorError("username must not be empty")
    if not 1 <= int(config["history_days"]) <= 365:
        raise GeneratorError("history_days must be between 1 and 365")
    if not 0 <= int(config["max_languages"]) <= 30:
        raise GeneratorError("max_languages must be between 0 and 30")
    if int(config["width"]) < 300 or int(config["height"]) < 180:
        raise GeneratorError("width must be >= 300 and height must be >= 180")
    for name, colour in config.get("color_overrides", {}).items():
        if not HEX_COLOUR.fullmatch(colour):
            raise GeneratorError(f"Invalid color_overrides value for {name!r}: {colour!r}")
    try:
        ZoneInfo(str(config["timezone"]))
    except ZoneInfoNotFoundError as exc:
        raise GeneratorError(f"Unknown timezone: {config['timezone']}") from exc


def target_day(timezone_name: str, now: datetime | None = None) -> date:
    zone = ZoneInfo(timezone_name)
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(zone).date() - timedelta(days=1)


def resolve_username(username: str) -> str:
    raw = http_text(f"https://codestats.net/api/users/{quote(username, safe='')}")
    try:
        payload = json.loads(raw)
        return str(payload["user"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise GeneratorError("Code::Stats returned an invalid user response") from exc


def fetch_range(username: str, start_day: date, end_day: date) -> dict[str, dict[str, int]]:
    if end_day < start_day:
        raise GeneratorError("end_day must not be earlier than start_day")
    graphql_username = json.dumps(username, ensure_ascii=False)
    start_text = start_day.isoformat()
    query = (
        "{\n"
        f"  profile(username: {graphql_username}) {{\n"
        f'    day_language_xps: dayLanguageXps(since: "{start_text}") '
        "{ date language xp }\n"
        "  }\n"
        "}\n"
    )
    raw = http_text("https://codestats.net/profile-graph", data=query.encode("utf-8"))
    try:
        payload = json.loads(raw)
        if payload.get("errors"):
            raise GeneratorError(f"Code::Stats GraphQL error: {payload['errors']}")
        rows = payload["data"]["profile"]["day_language_xps"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise GeneratorError("Code::Stats returned an invalid history response") from exc

    result: dict[str, defaultdict[str, int]] = {}
    cursor = start_day
    while cursor <= end_day:
        result[cursor.isoformat()] = defaultdict(int)
        cursor += timedelta(days=1)

    for row in rows:
        # The API has no `until` argument. This bound check guarantees that a
        # run never stores today's partial data or anything outside its window.
        row_day = _safe_date(row.get("date"))
        if row_day is None or not start_day <= row_day <= end_day:
            continue
        language = str(row.get("language", "")).strip()
        xp = int(row.get("xp", 0))
        if language and xp > 0:
            result[row_day.isoformat()][language] += xp
    return {
        day_text: dict(sorted(languages.items(), key=lambda item: item[0].casefold()))
        for day_text, languages in result.items()
    }


def fetch_day(username: str, day: date) -> dict[str, int]:
    return fetch_range(username, day, day)[day.isoformat()]


def _yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_linguist_colours(source: str) -> dict[str, str]:
    """Parse the small subset of languages.yml needed for names and colours."""
    records: dict[str, dict[str, Any]] = {}
    current: str | None = None
    in_aliases = False

    for line in source.splitlines():
        if line and not line[0].isspace() and line.endswith(":") and not line.startswith("---"):
            current = _yaml_scalar(line[:-1])
            records.setdefault(current, {"aliases": []})
            in_aliases = False
            continue
        if current is None:
            continue
        colour_match = re.match(r'^  color:\s*["\']?(#[0-9a-fA-F]{6})', line)
        if colour_match:
            records[current]["color"] = colour_match.group(1).lower()
            in_aliases = False
            continue
        group_match = re.match(r"^  group:\s*(.+?)\s*$", line)
        if group_match:
            records[current]["group"] = _yaml_scalar(group_match.group(1))
            in_aliases = False
            continue
        if line == "  aliases:":
            in_aliases = True
            continue
        if in_aliases:
            alias_match = re.match(r"^  -\s*(.+?)\s*$", line)
            if alias_match:
                records[current]["aliases"].append(_yaml_scalar(alias_match.group(1)))
                continue
            in_aliases = False

    def inherited_colour(name: str, seen: set[str] | None = None) -> str | None:
        seen = seen or set()
        if name in seen or name not in records:
            return None
        seen.add(name)
        record = records[name]
        return record.get("color") or inherited_colour(record.get("group", ""), seen)

    colours: dict[str, str] = {}
    for name, record in records.items():
        colour = inherited_colour(name)
        if not colour:
            continue
        colours[name] = colour
        for alias in record["aliases"]:
            colours.setdefault(alias, colour)
    if len(colours) < 300:
        raise GeneratorError("The GitHub Linguist colour file was not parsed correctly")
    return dict(sorted(colours.items(), key=lambda item: item[0].casefold()))


def refresh_colours(cache_path: Path) -> dict[str, str]:
    try:
        colours = parse_linguist_colours(http_text(LINGUIST_URL))
        write_json(cache_path, colours)
        print(f"Updated {cache_path.relative_to(ROOT)} from GitHub Linguist ({len(colours)} names).")
        return colours
    except GeneratorError as exc:
        if cache_path.exists():
            print(f"Warning: {exc}; using cached GitHub colours.", file=sys.stderr)
            cached = load_json(cache_path)
            return {str(name): str(value) for name, value in cached.items()}
        raise


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(rendered, encoding="utf-8", newline="\n")


def update_history(
    history: dict[str, Any], username: str, day: date, languages: dict[str, int], keep_days: int
) -> dict[str, Any]:
    previous_username = str(history.get("username", ""))
    if previous_username and previous_username.casefold() != username.casefold():
        # A fork that changes the configured account must never mix two users'
        # XP in the same graph.
        days = {}
    else:
        days = history.get("days", {})
    if not isinstance(days, dict):
        raise GeneratorError("history file has an invalid 'days' value")
    days[day.isoformat()] = languages
    cutoff = day - timedelta(days=keep_days - 1)
    kept_days = {
        key: value
        for key, value in days.items()
        if _safe_date(key) is not None and _safe_date(key) >= cutoff
    }
    return {
        "username": username,
        "bootstrap_complete": bool(history.get("bootstrap_complete", False)),
        "days": dict(sorted(kept_days.items())),
    }


def _safe_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def nice_y_axis(maximum: int) -> tuple[int, int]:
    maximum = max(1, maximum)
    exponent = math.floor(math.log10(maximum))
    fraction = maximum / (10**exponent)
    nice_fraction = next(value for value in (1, 2, 5, 10) if value >= fraction)
    tick = max(1, int(nice_fraction * (10 ** (exponent - 1))))
    ceiling = math.ceil(maximum / tick) * tick
    return ceiling, tick


def colour_for(language: str, config: dict[str, Any], colours: dict[str, str]) -> str:
    overrides = config.get("color_overrides", {})
    if language in overrides:
        return overrides[language].lower()
    aliases = config.get("language_aliases", {})
    lookup = str(aliases.get(language, language))
    folded = {name.casefold(): colour for name, colour in colours.items()}
    return folded.get(lookup.casefold(), str(config.get("unknown_color", "#d0d7de"))).lower()


def graph_series(
    days: dict[str, dict[str, int]], date_range: list[date], max_languages: int
) -> list[tuple[str, list[int]]]:
    by_language: defaultdict[str, list[int]] = defaultdict(lambda: [0] * len(date_range))
    for index, day in enumerate(date_range):
        for language, xp in days.get(day.isoformat(), {}).items():
            by_language[language][index] += int(xp)
    ordered = sorted(by_language.items(), key=lambda item: (-sum(item[1]), item[0].casefold()))
    if len(ordered) <= max_languages:
        return ordered
    others = [sum(values) for values in zip(*(values for _, values in ordered[max_languages:]))]
    return ordered[:max_languages] + [("Others", others)]


def render_svg(
    history: dict[str, Any], end_day: date, config: dict[str, Any], colours: dict[str, str]
) -> str:
    width, height = int(config["width"]), int(config["height"])
    history_days = int(config["history_days"])
    date_range = [end_day - timedelta(days=offset) for offset in range(history_days - 1, -1, -1)]
    series = graph_series(history.get("days", {}), date_range, int(config["max_languages"]))
    show_legend = bool(config["show_legend"] and series)

    left, top, bottom = 64.0, 10.0, height - 53.0
    legend_width = 0.0
    if show_legend:
        longest_label = max(len(language) for language, _ in series)
        legend_width = min(width * 0.35, max(145.0, 48.0 + longest_label * 6.4))
    right = width - (legend_width if show_legend else 18.0)
    plot_width, plot_height = right - left, bottom - top
    slot = plot_width / history_days
    bar_width = slot * 0.70
    daily_totals = [sum(values[index] for _, values in series) for index in range(history_days)]
    y_max, tick = nice_y_axis(max(daily_totals, default=0))
    ticks = list(range(0, y_max + 1, tick))

    bg = str(config.get("background_color", "#ffffff"))
    grid = str(config.get("grid_color", "#d0d7de"))
    text = str(config.get("text_color", "#57606a"))
    zero = str(config.get("zero_line_color", "#8c959f"))
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{escape(history.get('username', config['username']))}'s Code::Stats history graph</title>",
        f'<desc id="desc">Code::Stats XP per language for the {history_days} days ending {end_day.isoformat()}.</desc>',
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
        f'<g font-family="{font}" font-size="12" fill="{text}">',
    ]

    for index in range(history_days):
        x = left + slot * (index + 0.5)
        parts.append(
            f'<line x1="{x:.2f}" y1="{top:.2f}" x2="{x:.2f}" y2="{bottom:.2f}" '
            f'stroke="{grid}" stroke-width="1" opacity="0.58"/>'
        )
    for value in ticks:
        y = bottom - (value / y_max) * plot_height
        colour = zero if value == 0 else grid
        parts.append(
            f'<line x1="{left:.2f}" y1="{y:.2f}" x2="{right:.2f}" y2="{y:.2f}" '
            f'stroke="{colour}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8:.2f}" y="{y + 4:.2f}" text-anchor="end">{value:,}</text>'
        )

    for day_index in range(history_days):
        x = left + slot * (day_index + 0.5) - bar_width / 2
        accumulated = 0
        for language, values in series:
            value = values[day_index]
            if value <= 0:
                continue
            rect_height = value / y_max * plot_height
            y = bottom - (accumulated + value) / y_max * plot_height
            parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{rect_height:.2f}" '
                f'fill="{colour_for(language, config, colours)}"><title>{escape(language)}: {value:,} XP</title></rect>'
            )
            accumulated += value

    label_y = bottom + 13
    for index, day in enumerate(date_range):
        x = left + slot * (index + 0.5)
        label = f"{MONTHS[day.month - 1]} {day.day}"
        parts.append(
            f'<text x="{x:.2f}" y="{label_y:.2f}" text-anchor="end" '
            f'transform="rotate(-45 {x:.2f} {label_y:.2f})">{label}</text>'
        )
    title_x, title_y = 20.0, top + plot_height / 2
    parts.append(
        f'<text x="{title_x}" y="{title_y:.2f}" text-anchor="middle" '
        f'transform="rotate(-90 {title_x} {title_y:.2f})">XP</text>'
    )

    if show_legend:
        legend_x = right + 17
        for index, (language, _) in enumerate(series):
            y = top + 8 + index * 18
            colour = colour_for(language, config, colours)
            parts.append(f'<rect x="{legend_x:.2f}" y="{y:.2f}" width="12" height="12" fill="{colour}"/>')
            parts.append(
                f'<text x="{legend_x + 27:.2f}" y="{y + 10:.2f}" font-size="12">{escape(language)}</text>'
            )

    parts.extend(("</g>", "</svg>", ""))
    return "\n".join(parts)


def relative_path(value: str, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--date", type=date.fromisoformat, help="day to fetch (YYYY-MM-DD); defaults to yesterday")
    parser.add_argument("--bootstrap", action="store_true", help="refresh the complete history window")
    parser.add_argument("--offline", action="store_true", help="render stored data without network requests")
    parser.add_argument(
        "--workspace",
        type=Path,
        help="write history and SVG into another repository (used by the reusable action)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config.resolve())
    validate_config(config)
    workspace = args.workspace.resolve() if args.workspace else ROOT
    history_path = relative_path(config["history_file"], workspace)
    output_path = relative_path(config["output"], workspace)
    colours_path = relative_path(config["colors_file"])
    history = load_json(history_path) if history_path.exists() else {"days": {}}

    if args.offline:
        if not colours_path.exists():
            raise GeneratorError("--offline requires an existing colours cache")
        colours = load_json(colours_path)
        stored = [_safe_date(value) for value in history.get("days", {})]
        valid_stored = [value for value in stored if value is not None]
        end_day = args.date or (max(valid_stored) if valid_stored else target_day(config["timezone"]))
    else:
        day = args.date or target_day(config["timezone"])
        username = resolve_username(str(config["username"]))
        previous_username = str(history.get("username", ""))
        username_changed = bool(previous_username and previous_username.casefold() != username.casefold())
        needs_bootstrap = args.bootstrap or username_changed or not history.get("bootstrap_complete", False)
        if needs_bootstrap:
            first_day = day - timedelta(days=int(config["history_days"]) - 1)
            days = fetch_range(username, first_day, day)
            history = {"username": username, "bootstrap_complete": True, "days": days}
            total_xp = sum(sum(languages.values()) for languages in days.values())
            language_count = len({language for languages in days.values() for language in languages})
            print(
                f"Bootstrapped {len(days)} days ({total_xp:,} XP across "
                f"{language_count} languages) from {first_day} through {day}."
            )
        else:
            languages = fetch_day(username, day)
            history = update_history(history, username, day, languages, int(config["history_days"]))
            print(f"Stored {sum(languages.values()):,} XP across {len(languages)} languages for {day}.")
        write_json(history_path, history)
        colours = refresh_colours(colours_path)
        end_day = max(day, *(_safe_date(value) for value in history["days"] if _safe_date(value) is not None))

    svg = render_svg(history, end_day, config, colours)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8", newline="\n")
    print(f"Rendered {output_path.relative_to(workspace)} through {end_day}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
