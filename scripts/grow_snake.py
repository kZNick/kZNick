"""Extend snk's SVG body as contribution cells are eaten. No runtime JS needed."""

from bisect import bisect_right
from pathlib import Path
import math
import re
import sys
import xml.etree.ElementTree as ET

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
INITIAL_LENGTH = 4
MAX_LENGTH = 48  # Keep a busy calendar readable and the SVG lightweight.


def head_frames(css):
    match = re.search(r"@keyframes s0\{(.*?)\}\s*\}", css, re.S)
    if not match:
        raise ValueError("A trajetória da cabeça não foi encontrada no SVG do snk.")
    frames = {}
    for selectors, x, y in re.findall(
        r"([\d.% ,]+)\{transform:translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)",
        match[1],
    ):
        for value in re.findall(r"([\d.]+)%", selectors):
            frames[float(value)] = (float(x), float(y))
    if not frames or 0 not in frames:
        raise ValueError("Trajetória da cabeça inválida.")
    frames.setdefault(100.0, frames[0])
    return sorted(frames.items())


def position(frames, time, step):
    if time < 0:
        # Initial body extends to the right, matching snk's initial pose.
        x, y = frames[0][1]
        return x - time / step * 16, y
    times = [frame[0] for frame in frames]
    index = max(0, bisect_right(times, time) - 1)
    if index == len(frames) - 1:
        return frames[index][1]
    t0, (x0, y0) = frames[index]
    t1, (x1, y1) = frames[index + 1]
    progress = (time - t0) / (t1 - t0)
    return x0 + (x1 - x0) * progress, y0 + (y1 - y0) * progress


def eating_times(css):
    # snk changes each occupied cell to --ce at the moment it gets eaten.
    return sorted(float(value) for value in re.findall(
        r"([\d.]+)%,100%\{fill:var\(--ce\)\}", css
    ))


def enhance(svg):
    root = ET.fromstring(svg)
    if root.get("data-growing-snake"):
        raise ValueError("Este SVG já recebeu a animação de crescimento.")
    style = root.find(f"{{{NS}}}style")
    if style is None:
        raise ValueError("SVG sem estilos.")
    css = style.text or ""
    frames = head_frames(css)
    # Find the actual time taken to travel one 16px calendar cell.
    steps = []
    for (t0, (x0, y0)), (t1, (x1, y1)) in zip(frames, frames[1:]):
        distance = abs(x1 - x0) + abs(y1 - y0)
        if distance and (x0 == x1 or y0 == y1):
            steps.append((t1 - t0) * 16 / distance)
    if not steps:
        raise ValueError("A trajetória precisa conter movimento.")
    step = sorted(steps)[len(steps) // 2]
    eats = eating_times(css)
    capacity = MAX_LENGTH - INITIAL_LENGTH
    count = min(len(eats), capacity)
    # Grow on every occupied day, or distribute growth over dense calendars.
    births = [0.0] * INITIAL_LENGTH + [
        eats[math.ceil((i + 1) * len(eats) / count) - 1]
        for i in range(count)
    ]
    duration = max(24000, int(re.search(r"(\d+)ms", css)[1]))
    css = re.sub(r"\d+ms", f"{duration}ms", css)
    for element in list(root):
        if "s" in element.get("class", "").split():
            root.remove(element)
    rules = []
    group = ET.SubElement(root, f"{{{NS}}}g", {"class": "growing-snake"})
    # Draw the tail first so the head remains visible when the path crosses.
    for index in reversed(range(len(births))):
        birth = births[index]
        delay = index * step
        times = sorted({0.0, 100.0, birth} | {
            t + delay for t, _ in frames if 0 < t + delay < 100
        })
        transforms = []
        for time in times:
            x, y = position(frames, time - delay, step)
            transforms.append(f"{time:.5f}%{{transform:translate({x:.3f}px,{y:.3f}px)}}")
        name = f"growing-move-{index}"
        rules.append(f"@keyframes {name}{{{''.join(transforms)}}}")
        show = f"growing-show-{index}"
        if index >= INITIAL_LENGTH:
            before = max(0, birth - 0.0001)
            rules.append(f"@keyframes {show}{{0%,{before:.5f}%{{opacity:0}}{birth:.5f}%,100%{{opacity:1}}}}")
        size = 14.4 if index == 0 else 12.4
        offset = (16 - size) / 2
        x, y = position(frames, -delay, step)
        animations = f"{name} {duration}ms linear infinite"
        if index >= INITIAL_LENGTH:
            animations += f",{show} {duration}ms steps(1,end) infinite"
        ET.SubElement(group, f"{{{NS}}}rect", {
            "class": "growing-part",
            "data-born-at": f"{birth:.5f}",
            "x": f"{offset:.1f}", "y": f"{offset:.1f}",
            "width": str(size), "height": str(size), "rx": "4",
            "fill": "var(--cs)",
            "style": f"transform:translate({x:.3f}px,{y:.3f}px);animation:{animations}",
        })
    # Fade the body just before the loop resets to its initial length.
    rules.append(f".growing-snake{{animation:growing-loop {duration}ms linear infinite}}")
    rules.append("@keyframes growing-loop{0%,98%{opacity:1}100%{opacity:0}}")
    style.text = css + "".join(rules)
    root.set("data-growing-snake", "true")
    root.set("data-initial-length", str(INITIAL_LENGTH))
    root.set("data-final-length", str(len(births)))
    return ET.tostring(root, encoding="unicode")


if __name__ == "__main__":
    paths = [Path(value) for value in sys.argv[1:]]
    if not paths:
        raise SystemExit("Uso: python scripts/grow_snake.py dist/*.svg")
    for path in paths:
        result = enhance(path.read_text(encoding="utf-8"))
        path.write_text(result, encoding="utf-8")
        root = ET.fromstring(result)
        print(f"{path}: {root.get('data-initial-length')} → {root.get('data-final-length')} segmentos")
