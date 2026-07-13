# -*- coding: utf-8 -*-

from marshmallow import (
    Schema,
    fields,
    post_load,
    validate,
)

from app.fields import (
    ColorString,
    LanguageColors,
    TimezoneString,
)

from app.models.history_graph_config import GraphConfig


class GraphConfigSchema(Schema):
    history_days = fields.Integer(
        validate=validate.Range(
            min=1,
            max=30,
        )
    )

    max_languages = fields.Integer(
        validate=validate.Range(
            min=0,
            max=15,
        )
    )

    language_colors = LanguageColors()

    fallback_language_color = ColorString()

    timezone = TimezoneString()

    bg_color = ColorString()

    width = fields.Integer(
        validate=validate.Range(min=10)
    )

    height = fields.Integer(
        validate=validate.Range(min=10)
    )

    show_legend = fields.Boolean()

    grid_color = ColorString()

    text_color = ColorString()

    zeroline_color = ColorString()

    @post_load
    def make_object(
        self,
        data,
        **kwargs
    ) -> GraphConfig:
        config = GraphConfig()
        config.update(**data)

        return config