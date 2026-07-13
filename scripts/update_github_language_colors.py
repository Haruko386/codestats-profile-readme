import json
from pathlib import Path

import requests
import yaml


SOURCE_URL = (
    'https://raw.githubusercontent.com/github-linguist/linguist/'
    'main/lib/linguist/languages.yml'
)

PROJECT_PATH = Path(__file__).resolve().parents[1]

OUTPUT_PATH = (
    PROJECT_PATH
    / 'app'
    / 'data'
    / 'github_language_colors.json'
)


def resolve_language_color(language_name, languages, resolving=None):
    """Resolve a language color, including inherited group colors."""

    if resolving is None:
        resolving = set()

    if language_name in resolving:
        return None

    language = languages.get(language_name, {})

    color = language.get('color')
    if color:
        return color

    group = language.get('group')
    if not group:
        return None

    resolving.add(language_name)

    return resolve_language_color(
        group,
        languages,
        resolving,
    )


def build_language_color_data(languages):
    """Build canonical language colors and aliases."""

    colors = {}
    aliases = {}

    # First reserve every official language name.
    for language_name in languages:
        canonical_name = language_name.strip().lower()
        aliases[canonical_name] = canonical_name

    for language_name, language in languages.items():
        canonical_name = language_name.strip().lower()

        color = resolve_language_color(
            language_name,
            languages,
        )

        for alias in language.get('aliases', []):
            alias_name = str(alias).strip().lower()

            # Do not let aliases override official language names.
            aliases.setdefault(
                alias_name,
                canonical_name,
            )

        if color:
            colors[canonical_name] = color

    return {
        'source': SOURCE_URL,
        'colors': dict(sorted(colors.items())),
        'aliases': dict(sorted(aliases.items())),
    }


def main():
    """Download Linguist data and generate the local color file."""

    response = requests.get(
        SOURCE_URL,
        timeout=30,
    )
    response.raise_for_status()

    languages = yaml.safe_load(response.text)

    output = build_language_color_data(languages)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        'w',
        encoding='utf-8',
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        file.write('\n')

    print(
        'Wrote {} colors to {}'.format(
            len(output['colors']),
            OUTPUT_PATH,
        )
    )


if __name__ == '__main__':
    main()