#!/usr/bin/env python3
"""Regenerate the SVG charts using only the standard library."""
import argparse
import html
import json
from pathlib import Path

COLORS = {"ink": "#1a1a19", "ink2": "#52514e", "muted": "#8a8984",
          "before": "#a9a8a2", "after": "#2a78d6", "mid": "#8db6e8",
          "box": "#f3f2ee", "line": "#e4e3de"}


def text(x, y, value, size=13, fill="ink", bold=False, anchor=None):
    attributes = f' font-weight="700"' if bold else ""
    if anchor:
        attributes += f' text-anchor="{anchor}"'
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" '
            f'fill="{COLORS[fill]}"{attributes}>{html.escape(str(value))}</text>')


def rect(x, y, width, height, color):
    return (f'<rect x="{x:g}" y="{y:g}" width="{width:g}" '
            f'height="{height:g}" fill="{COLORS[color]}"/>')


def svg(height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" '
            f'viewBox="0 0 760 {height}" font-family="system-ui,sans-serif">\n'
            f'<rect width="760" height="{height}" rx="12" fill="#ffffff"/>\n{body}\n</svg>\n')


def legend(y, labels, colors=("before", "after")):
    return "".join(rect(24 + i * 150, y - 10, 12, 12, colors[i]) +
                   text(42 + i * 150, y, label, 12, "ink2") for i, label in enumerate(labels))


def title(labels, subtitle=True):
    result = text(24, 34, labels["title"], 18, bold=True)
    if subtitle:
        result += text(24, 56, labels["sub"], 12.5, "ink2")
    return result


def paired_rows(names, values, y, changes=(), colors=("before", "after"), row_height=62):
    body = ""
    for i, (name, pair) in enumerate(zip(names, values)):
        body += text(24, y + 22, name)
        if changes:
            body += text(24, y + 42, changes[i], 12.5, "ink2", True)
        for j, value in enumerate(pair):
            width = value / max(pair) * 360
            body += rect(330, y + 8 + j * 18, width, 14, colors[j])
            body += text(338 + width, y + 20 + j * 18, f"{value:,g}", 12.5,
                         "ink2" if j == 0 else "ink")
        y += row_height
    return body, y


def first_principles(labels):
    body = title(labels)
    body += rect(30, 76, 693, 30, "before") + rect(723, 76, 7, 30, "after")
    body += text(30, 126, labels["reread"], 13, "ink2")
    body += text(730, 126, labels["fresh"], 13, "after", anchor="end")
    body += text(380, 174, labels["formula"], 20, bold=True, anchor="middle")
    for i, (head_text, *lines) in enumerate(labels["levers"]):
        x = 24 + i * 242
        body += rect(x, 196, 228, 124, "box")
        body += text(x + 14, 222, head_text, 14.5, bold=True)
        for j, line in enumerate(lines):
            body += text(x + 14, 250 + j * 24, line, 12.5, "ink2")
    return svg(370, body + text(24, 352, labels["foot"], 11.5, "muted"))


def before_after(labels):
    body = title(labels) + legend(80, labels["legend"])
    values = [[10.5, 5.8], [3.67, 2.14], [51, 23], [33, 6]]
    rows, y = paired_rows(labels["rows"], values, 96, labels["chg"])
    return svg(y + 44, body + rows + text(24, y + 26, labels["foot"], 11.5, "muted"))


def generate(output):
    source = Path(__file__).with_name("chart-text.json")
    labels = json.loads(source.read_text(encoding="utf-8"))
    charts = [("first-principles", first_principles, "fp"), ("before-after", before_after, "ba")]
    for language in ["zh", "en"]:
        directory = output if language == "zh" else output / "en"
        directory.mkdir(parents=True, exist_ok=True)
        for name, render, key in charts:
            (directory / (name + ".svg")).write_text(render(labels[language][key]), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("images"))
    generate(parser.parse_args().out)
    print("Generated four charts.")
