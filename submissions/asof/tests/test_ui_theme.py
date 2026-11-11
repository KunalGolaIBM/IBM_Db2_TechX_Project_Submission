"""The console and the chat page are light by default on every machine, dark-mode ones included: the video and the
screenshots show the light UI, and a judge on a dark-mode laptop should see the same. The dark palette stays in the
stylesheets, but only an explicit <html data-theme="dark"> turns it on."""
from __future__ import annotations

import pathlib

import pytest

UI = pathlib.Path(__file__).resolve().parents[1] / "src" / "asof" / "ui"


@pytest.mark.parametrize("sheet", ["app.css", "chat.css"])
def test_light_is_the_default_whatever_the_system_setting(sheet):
    css = (UI / sheet).read_text()
    assert "prefers-color-scheme" not in css
    assert "color-scheme: light;" in css.split(":root[data-theme=")[0]  # the default :root block is light
    assert ':root[data-theme="dark"] {' in css  # the dark palette is still there, as an explicit opt-in


def test_no_page_turns_the_dark_theme_on():
    for page in [*UI.glob("*.html"), *UI.glob("*.js")]:
        text = page.read_text()
        assert 'data-theme="dark"' not in text and "dataset.theme" not in text, page.name
