#!/usr/bin/env python3
"""Render a portable status-aware PNG of a Blueprint v2.2 dependency graph."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TYPE_STYLES = {
    "problem_hypothesis": ("#fff2bf", "#9b7300", "H"),
    "definition_contract": ("#eef1f4", "#68737e", "Def"),
    "external_mathematical_result": ("#dceeff", "#2f72a2", "Ext"),
    "mathematical_claim": ("#e4f1ff", "#3378a8", "P"),
    "mathematical_inference": ("#f0e3ff", "#7d4ea1", "⇒"),
    "verified_counterexample": ("#ffe1e1", "#a04040", "CEx"),
    "research_goal": ("#fff0d7", "#aa671e", "Goal"),
    "proof_obligation": ("#fff5de", "#9c7327", "Obl"),
    "research_attempt": ("#f3e9dc", "#8b6741", "Try"),
    "basic_assumption": ("#fff2bf", "#9b7300", "A"),
    "theory_from_assumptions": ("#dceeff", "#2f72a2", "T1"),
    "numerical_method": ("#e1f4e8", "#357b57", "M"),
    "numerical_result": ("#d5f0df", "#287849", "N"),
    "numerical_experiment_design": ("#f3f3f3", "#747d86", "D"),
    "theory_from_numerics": ("#f0e3ff", "#7d4ea1", "T2"),
    "superseded": ("#f7e1e1", "#9d4b4b", "X"),
}
FALLBACK_STYLE = ("#eef1f4", "#68737e", "•")
BACKGROUND = "#f7f8fa"
INK = "#17202a"
MUTED = "#53606d"
EDGE = "#83909d"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, default=ROOT / "blueprint.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dependency_graph.png")
    return parser.parse_args()


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


TITLE_FONT = font(30, bold=True)
NODE_FONT = font(17, bold=True)
SMALL_FONT = font(13)
EDGE_FONT = font(11)


def normalize_edge(edge: Any) -> dict[str, str | None]:
    if isinstance(edge, list) and len(edge) == 2:
        return {"source": edge[0], "target": edge[1], "role": None}
    if isinstance(edge, dict) and edge.get("source") and edge.get("target"):
        return {
            "source": edge["source"],
            "target": edge["target"],
            "role": edge.get("role") or edge.get("relation"),
        }
    raise ValueError(f"invalid edge: {edge!r}")


def infer_role(source: str, target: dict[str, Any]) -> str:
    mapping = {
        "assumptions": "assumption",
        "theory_inputs": "theory_input",
        "method_inputs": "method_input",
        "numerical_inputs": "numerical_input",
        "premise_inputs": "premise_input",
        "definition_inputs": "definition_input",
        "inference_inputs": "inference_input",
        "refutation_inputs": "refutation_input",
        "target_inputs": "target_input",
    }
    for field, role in mapping.items():
        if source in target.get(field, []):
            return role
    return "dependency"


def topological_depth(node_ids: list[str], edges: list[dict[str, str | None]]) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        outgoing[source].append(target)
        indegree[target] += 1
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    depth = {node_id: 0 for node_id in node_ids}
    visited = 0
    while queue:
        source = queue.popleft()
        visited += 1
        for target in sorted(outgoing[source]):
            depth[target] = max(depth[target], depth[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_ids):
        raise ValueError("dependency graph contains a cycle; run validate_blueprint.py")
    return depth


def truncate(draw: ImageDraw.ImageDraw, value: str, width: int, used_font: ImageFont.ImageFont) -> str:
    text = " ".join(str(value).split())
    if draw.textlength(text, font=used_font) <= width:
        return text
    while text and draw.textlength(text + "…", font=used_font) > width:
        text = text[:-1]
    return text + "…"


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    mid_x = start[0] + (end[0] - start[0]) // 2
    points = [start, (mid_x, start[1]), (mid_x, end[1]), end]
    draw.line(points, fill=EDGE, width=2, joint="curve")
    angle = math.atan2(end[1] - points[-2][1], end[0] - points[-2][0])
    size = 8
    left = (end[0] - size * math.cos(angle - 0.55), end[1] - size * math.sin(angle - 0.55))
    right = (end[0] - size * math.cos(angle + 0.55), end[1] - size * math.sin(angle + 0.55))
    draw.polygon([end, left, right], fill=EDGE)


def main() -> int:
    args = parse_args()
    data = json.loads(args.blueprint.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("blueprint.nodes must be a list")
    by_id = {node["id"]: node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("node IDs must be unique")
    edges = [normalize_edge(edge) for edge in data.get("edges", [])]
    for edge in edges:
        if edge["source"] not in by_id or edge["target"] not in by_id:
            raise ValueError(f"edge references an unknown endpoint: {edge}")
        if not edge["role"]:
            edge["role"] = infer_role(str(edge["source"]), by_id[str(edge["target"])])

    margin = 54
    header = 105
    node_width = 330
    node_height = 104
    x_gap = 105
    y_gap = 36

    if nodes:
        depth = topological_depth(list(by_id), edges)
        levels: dict[int, list[str]] = defaultdict(list)
        for node_id in sorted(by_id):
            levels[depth[node_id]].append(node_id)
        max_depth = max(levels)
        max_rows = max(len(node_ids) for node_ids in levels.values())
        width = margin * 2 + (max_depth + 1) * node_width + max_depth * x_gap
        height = header + margin + max_rows * node_height + max(0, max_rows - 1) * y_gap + margin
        positions: dict[str, tuple[int, int, int, int]] = {}
        for level in range(max_depth + 1):
            members = levels.get(level, [])
            column_height = len(members) * node_height + max(0, len(members) - 1) * y_gap
            y = header + margin + max(0, (height - header - 2 * margin - column_height) // 2)
            x = margin + level * (node_width + x_gap)
            for node_id in members:
                positions[node_id] = (x, y, x + node_width, y + node_height)
                y += node_height + y_gap
    else:
        width, height = 1100, 360
        positions = {}

    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    title = data.get("project", {}).get("title") or data.get("project", {}).get("id") or "Blueprint v2.2"
    draw.text((margin, 28), str(title), font=TITLE_FONT, fill=INK)
    draw.text(
        (margin, 69),
        f"{len(nodes)} nodes · {len(edges)} typed dependencies · status-aware mathematics graph",
        font=SMALL_FONT,
        fill=MUTED,
    )

    if not nodes:
        draw.text((margin, 170), "The canonical graph is empty.", font=NODE_FONT, fill=MUTED)
    else:
        for edge in edges:
            source_box = positions[str(edge["source"])]
            target_box = positions[str(edge["target"])]
            start = (source_box[2], (source_box[1] + source_box[3]) // 2)
            end = (target_box[0], (target_box[1] + target_box[3]) // 2)
            arrow(draw, start, end)
            label_x = start[0] + (end[0] - start[0]) // 2 + 4
            label_y = min(start[1], end[1]) + abs(end[1] - start[1]) // 2 - 14
            draw.text((label_x, label_y), str(edge["role"]), font=EDGE_FONT, fill=MUTED)

        for node_id, box in positions.items():
            node = by_id[node_id]
            fill, stroke, marker = TYPE_STYLES.get(node.get("epistemic_type"), FALLBACK_STYLE)
            draw.rounded_rectangle(box, radius=14, fill=fill, outline=stroke, width=3)
            x1, y1, x2, y2 = box
            heading = truncate(draw, f"[{marker}] {node.get('title', node_id)}", node_width - 24, NODE_FONT)
            statement = truncate(draw, node.get("statement", ""), node_width - 24, SMALL_FONT)
            draw.text((x1 + 12, y1 + 10), heading, font=NODE_FONT, fill=INK)
            draw.text((x1 + 12, y1 + 40), statement, font=SMALL_FONT, fill=MUTED)
            status = node.get("status", "unknown")
            grade = node.get("grade", "—")
            draw.text((x1 + 12, y2 - 24), f"{node_id} · {status} · grade {grade}", font=SMALL_FONT, fill=MUTED)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="PNG", optimize=True)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
