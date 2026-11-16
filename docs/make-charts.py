#!/usr/bin/env python3
"""Regenerate the historical SVG charts using only the standard library."""
import argparse
import html
import json
from pathlib import Path

COLORS = {"ink": "#1a1a19", "ink2": "#52514e", "muted": "#8a8984",
          "before": "#a9a8a2", "after": "#2a78d6", "mid": "#8db6e8",
          "slow": "#eb6834", "both": "#c9a227"}


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


def staircase(labels):
    body = title(labels) + '<line x1="30" y1="270" x2="740" y2="270" stroke="#e4e3de"/>'
    values = [10.5, 9.8, 9.9, 9.2, 7.5, 6.4]
    for i, (name, date) in enumerate(labels["bars"]):
        x, height = 40 + i * 116, values[i] * 16
        color = "before" if i == 0 else "after" if i == 5 else "mid"
        body += rect(x, 270 - height, 72, height, color)
        body += text(x + 36, 262 - height, f"{values[i]:.1f}", 15, bold=True, anchor="middle")
        body += text(x + 36, 290, name, 12.5, anchor="middle")
        body += text(x + 36, 308, date, 11.5, "muted", anchor="middle")
    return svg(360, body + text(24, 346, labels["foot"], 11.5, "muted"))


def before_after(labels):
    body, y = title(labels) + legend(80, labels["legend"]), 96
    groups = [("good", "goodRows", [[10.5, 6.4], [3.67, 2.08], [51, 16], [3.1, 5.4]], 0),
              ("bad", "badRows", [[16.6, 19.7], [2020, 1588], [17, 44], [33, 43]], 4)]
    for heading, names, values, offset in groups:
        y += 22
        body += text(24, y, labels[heading], 14.5, bold=True)
        group, y = paired_rows(labels[names], values, y + 12, labels["chg"][offset:offset + 4])
        body += group
    return svg(700, body + text(24, 686, labels["foot"], 11.5, "muted"))


def test_wait(labels):
    body, x = title(labels), 30
    for i, value in enumerate([479, 126, 111]):
        width = value / 716 * 700
        body += rect(x, 84, width - 2, 34, ["after", "slow", "both"][i])
        body += text(x + 6, 140, f'{labels["parts"][i]} {value} {labels["times"]}')
        body += text(x + 6, 158, f"{value / 716 * 100:.0f}%", 12.5, "ink2", True)
        x += width
    for y, value in zip([200, 220, 252, 274, 294], labels["lines"] + [labels["fix"]] + labels["fixes"]):
        body += text(24, y, value, 13.5 if y == 252 else 13, bold=y == 252)
    return svg(330, body + text(24, 318, labels["foot"], 11.5, "muted"))


def sub_vs_session(labels):
    body = title(labels, False) + legend(64, labels["legend"], ("after", "before"))
    rows, y = paired_rows(labels["rows"], [[5.2, 9.1], [75, 110], [916, 656]], 80,
                          colors=("after", "before"), row_height=52)
    body += rows + text(24, y + 32, labels["lines"][0]) + text(24, y + 52, labels["lines"][1])
    return svg(300, body)


def codex_vs_claude(labels):
    values = [[38.0, 20.8], [15.3, 20.7], [57, 15], [22, 10]]
    values[:2] = [[round(v * labels["scale"], 1) for v in pair] for pair in values[:2]]
    body = title(labels) + legend(80, labels["legend"])
    rows, _ = paired_rows(labels["rows"], values, 96, labels["chg"])
    return svg(394, body + rows + text(24, 380, labels["foot"], 11.5, "muted"))


def generate(output):
    source = Path(__file__).with_name("chart-text.json")
    labels = json.loads(source.read_text(encoding="utf-8"))
    charts = [("cost-per-step", staircase, "stair"), ("before-after", before_after, "ba"),
              ("test-wait", test_wait, "tw"), ("subagent-vs-session", sub_vs_session, "sv"),
              ("codex-vs-claude", codex_vs_claude, "cx")]
    for language in ["zh", "en"]:
        directory = output if language == "zh" else output / "en"
        directory.mkdir(parents=True, exist_ok=True)
        for name, render, key in charts:
            (directory / (name + ".svg")).write_text(render(labels[language][key]), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("images"))
    generate(parser.parse_args().out)
    print("Generated ten historical charts; measurements unchanged.")
