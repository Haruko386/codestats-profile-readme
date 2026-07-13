# -*- coding: utf-8 -*-
import re
import json
import arrow

from json.decoder import JSONDecodeError
from _plotly_utils.basevalidators import ColorValidator
from dateutil.tz import tzoffset
from marshmallow import fields, ValidationError
from app.utils.language_colors import (
    normalize_language_color_overrides,
)


class ColorString(fields.String):
    def _deserialize(self, value, attr, data, **kwargs):
        super()._deserialize(value, attr, data, **kwargs)
        try:
            # 'aaa' -> '#aaa', 'aabbcc' -> '#aabbcc'
            if re.fullmatch(r'[0-9A-Fa-f]*', value) and len(value) in (3, 6):
                value = '#' + value
            return ColorValidator('', '').validate_coerce(value)
        except ValueError as err:
            raise ValidationError(f'Invalid color string: {value}') from err

class LanguageColors(fields.Field):
    """Deserialize positional palettes or language color mappings."""

    def _deserialize(
        self,
        value,
        attr,
        data,
        **kwargs
    ):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except JSONDecodeError as err:
                raise ValidationError(
                    'Invalid language_colors JSON: {}'.format(
                        value
                    )
                ) from err

        color_field = ColorString()

        # Legacy syntax:
        # ["red", "green", "blue"]
        if isinstance(value, list):
            if not value:
                raise ValidationError(
                    'language_colors list cannot be empty'
                )

            return [
                color_field.deserialize(color)
                for color in value
            ]

        # New syntax:
        # {"Python": "ff0000", "cpp": "00ff00"}
        if isinstance(value, dict):
            parsed_colors = {}

            for language, color in value.items():
                if (
                    not isinstance(language, str)
                    or not language.strip()
                ):
                    raise ValidationError(
                        'Language name must be a non-empty string'
                    )

                parsed_colors[language.strip()] = (
                    color_field.deserialize(color)
                )

            return normalize_language_color_overrides(
                parsed_colors
            )

        raise ValidationError(
            'language_colors must be a JSON object '
            'or JSON list'
        )


class TimezoneString(fields.String):
    def _deserialize(self, value, attr, data, **kwargs):
        super()._deserialize(value, attr, data, **kwargs)
        try:
            value = value.strip()
            parsed = arrow.parser.TzinfoParser.parse(value)
            if isinstance(parsed, tzoffset):
                offset = parsed.utcoffset(None).total_seconds()
                if not -12 <= offset / 60 / 60 <= 12:
                    raise ValidationError(f'Invalid timezone string: {value}, must between -12:00 and +12:00')
            return value
        except arrow.ParserError as err:
            raise ValidationError(f'Invalid timezone string: {value}') from err
