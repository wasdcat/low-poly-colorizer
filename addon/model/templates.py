# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Layer 1: bundled palette templates (pure, no bpy).

A template is a JSON file in `addon/templates/` in the LPC file format
(`version: 2`, a `palette` section, optionally a display `name`). Loading a
template is an import from this folder -- the same format users export.
"""

import json
from pathlib import Path

from . import palette as model_palette

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_TEMPLATE = "stylized_3d"
FILE_VERSION = 2


def read_palette_file(text):
    """(name or None, palette) from the text of an LPC file with a
    `palette` section. Raises ValueError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("not valid JSON: %s" % exc) from None
    if not isinstance(data, dict):
        raise ValueError("file must contain a JSON object")
    if data.get("version") != FILE_VERSION:
        raise ValueError("unsupported version %r (expected %d)"
                         % (data.get("version"), FILE_VERSION))
    if "palette" not in data:
        raise ValueError("file has no palette section")
    name = data.get("name")
    return (str(name) if name is not None else None,
            model_palette.palette_from_json(data["palette"]))


def write_palette_file(palette, name=None):
    """Text of an LPC file holding `palette` (and a display `name`)."""
    data = {"version": FILE_VERSION}
    if name:
        data["name"] = name
    data["palette"] = model_palette.palette_to_json(palette)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def list_templates():
    """[(slug, display name)] of the bundled templates, sorted by name; a
    file that doesn't parse is skipped."""
    result = []
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            name, _palette = read_palette_file(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        result.append((path.stem, name or path.stem))
    result.sort(key=lambda item: item[1].lower())
    return result


def load_template(slug):
    """The palette of bundled template `slug`. Raises ValueError / OSError."""
    path = TEMPLATE_DIR / (slug + ".json")
    _name, palette = read_palette_file(path.read_text(encoding="utf-8"))
    return palette
