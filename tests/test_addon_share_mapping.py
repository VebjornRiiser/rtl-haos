"""Regression tests for add-on /share mapping.

The changelog claim:
  "Add-on now maps `/share` so config files can be dropped into the host share
   and referenced from the add-on."

This test is intentionally static/fast: it validates the add-on manifest
(`config.yaml`) declares a share mount under `map:`.

We intentionally avoid adding a YAML parser dependency. The `map:` section is
simple enough to parse with indentation-aware line scanning.
"""

from __future__ import annotations

from pathlib import Path


def _parse_map_entries(cfg_text: str) -> list[str]:
    """Return items under top-level `map:` (e.g. ['config', 'share:rw'])."""
    lines = cfg_text.splitlines()
    map_indent = None
    items: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "map:":
            map_indent = len(line) - len(line.lstrip(" "))
            # Consume subsequent indented list entries
            for nxt in lines[i + 1 :]:
                if not nxt.strip():
                    continue
                indent = len(nxt) - len(nxt.lstrip(" "))
                if indent <= map_indent:
                    break  # next top-level key
                lstripped = nxt.lstrip(" ")
                if not lstripped.startswith("-"):
                    continue
                item = lstripped[1:].strip()
                if item:
                    items.append(item)
            break

    return items


def test_addon_config_declares_share_mapping():
    repo_root = Path(__file__).resolve().parents[1]
    cfg = repo_root / "config.yaml"
    assert cfg.exists(), f"Expected add-on manifest at {cfg}"

    items = _parse_map_entries(cfg.read_text(encoding="utf-8"))

    # Normalize items like "share:rw" -> "share"
    base = {it.split(":", 1)[0].strip() for it in items}

    assert "share" in base, (
        "Add-on manifest must map the host /share directory so users can reference files "
        "from inside the add-on.\n\n"
        f"Found map entries: {items!r}\n"
        "Expected one of: 'share', 'share:ro', 'share:rw'"
    )
