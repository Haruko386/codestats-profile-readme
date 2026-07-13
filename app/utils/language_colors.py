# -*- coding: utf-8 -*-

import json
from pathlib import Path
from typing import Dict, Optional


_COLOR_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / 'data'
    / 'github_language_colors.json'
)


def _load_language_color_data():
    """Load GitHub language colors from the generated JSON file."""

    try:
        with _COLOR_DATA_PATH.open(
            'r',
            encoding='utf-8',
        ) as file:
            data = json.load(file)
    except (OSError, ValueError) as err:
        raise RuntimeError(
            'Cannot load GitHub language colors from {}'.format(
                _COLOR_DATA_PATH
            )
        ) from err

    return (
        data.get('colors', {}),
        data.get('aliases', {}),
    )


GITHUB_LANGUAGE_COLORS, GITHUB_LANGUAGE_ALIASES = (
    _load_language_color_data()
)


def normalize_language_name(language: str) -> str:
    """Normalize a language name or alias to its canonical name."""

    key = language.strip().lower()

    return GITHUB_LANGUAGE_ALIASES.get(
        key,
        key,
    )


def get_github_language_color(
    language: str,
) -> Optional[str]:
    """Return the official GitHub color for a language."""

    language_name = normalize_language_name(language)

    return GITHUB_LANGUAGE_COLORS.get(language_name)


def normalize_language_color_overrides(
    colors: Dict[str, str],
) -> Dict[str, str]:
    """Normalize language names in a custom color mapping."""

    return {
        normalize_language_name(language): color
        for language, color in colors.items()
    }