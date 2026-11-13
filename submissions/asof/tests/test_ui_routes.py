"""Every console page paints the shared view only while its own route is shown, so a slow answer (an Ask, a preview,
a backtest poll) that lands after the visitor has moved on cannot overwrite the next page. Ask the ledger, for
example, re-renders itself when its answer arrives; without the check, an answer that arrived after the visitor
opened Change impact would be drawn over it."""
from __future__ import annotations

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[1] / "src" / "asof" / "ui" / "app.js"


def test_every_page_mount_checks_its_route():
    text = APP.read_text()
    mounts = re.findall(r"^\s*(.*)mount\(view,", text, flags=re.M)
    unguarded = [m for m in mounts if not re.search(r'onRoute\("[a-z]+"\) && $', m)]
    # the router's own error box is the one exception: it paints for whatever route is current
    assert mounts and unguarded == [""], unguarded


def test_every_guard_names_a_real_route():
    text = APP.read_text()
    names = set(re.findall(r'onRoute\("([a-z]+)"\)', text))
    declared = set(re.findall(r"(\w+): \w+", re.search(r"const routes = \{([^}]*)\}", text)[1]))
    assert names and names <= declared
