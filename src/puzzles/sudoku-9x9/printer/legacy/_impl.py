#!/usr/bin/env python3
"""Generate a landscape PDF with Sudoku puzzles using project configuration."""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import math
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

SRC_ROOT = Path(__file__).resolve().parents[4]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from project_config import get_config
from artifacts import artifact_store
from ports import solver_port


CONFIG = get_config()
PDF_CONFIG = CONFIG.get("pdf", {})
LAYOUT_CONFIG = PDF_CONFIG.get("layout", {})
PAGE_CONFIG = PDF_CONFIG.get("page", {})
RENDER_CONFIG = PDF_CONFIG.get("rendering", {})
OUTPUT_CONFIG = PDF_CONFIG.get("output", {})
FALLBACK_CONFIG = PDF_CONFIG.get("fallback", {})


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _default_puzzle_kind() -> str:
    run_cfg = _as_dict(CONFIG.get("run"))
    value = run_cfg.get("puzzle_kind")
    if isinstance(value, str) and value:
        return value

    puzzle_cfg = _as_dict(CONFIG.get("PUZZLE"))
    fallback = puzzle_cfg.get("name")
    if isinstance(fallback, str) and fallback:
        return fallback

    return "sudoku-9x9"


def _build_solver_spec(puzzle_kind: str) -> Dict[str, Any]:
    puzzle_cfg = _as_dict(CONFIG.get("PUZZLE"))
    block_cfg = _as_dict(puzzle_cfg.get("block"))
    limits_cfg = _as_dict(CONFIG.get("LIMITS"))

    size = int(puzzle_cfg.get("size", 9))
    rows = int(block_cfg.get("rows", 3))
    cols = int(block_cfg.get("cols", 3))
    alphabet_raw = puzzle_cfg.get("alphabet", list("123456789"))
    if not isinstance(alphabet_raw, list):
        alphabet_raw = list("123456789")
    alphabet = [str(ch) for ch in alphabet_raw]

    timeout = limits_cfg.get("solver_timeout_ms", 1000)
    timeout_ms = int(timeout) if isinstance(timeout, (int, float)) else 1000

    return {
        "name": puzzle_kind,
        "size": size,
        "block": {"rows": rows, "cols": cols},
        "alphabet": alphabet,
        "limits": {"solver_timeout_ms": timeout_ms},
    }

LAYOUT_ROWS = int(LAYOUT_CONFIG.get("rows", 2))
LAYOUT_COLS = int(LAYOUT_CONFIG.get("cols", 2))
PUZZLES_PER_PAGE = max(1, LAYOUT_ROWS * LAYOUT_COLS)

_configured_total = PDF_CONFIG.get("total_puzzles")
_configured_pages = PDF_CONFIG.get("pages")
if _configured_total is None and _configured_pages is None:
    DEFAULT_TOTAL_PUZZLES = PUZZLES_PER_PAGE * 2
    DEFAULT_PAGES = 2
elif _configured_total is None:
    DEFAULT_PAGES = max(1, int(_configured_pages))
    DEFAULT_TOTAL_PUZZLES = DEFAULT_PAGES * PUZZLES_PER_PAGE
elif _configured_pages is None:
    DEFAULT_TOTAL_PUZZLES = max(1, int(_configured_total))
    DEFAULT_PAGES = max(1, math.ceil(DEFAULT_TOTAL_PUZZLES / PUZZLES_PER_PAGE))
else:
    DEFAULT_TOTAL_PUZZLES = max(1, int(_configured_total))
    DEFAULT_PAGES = max(1, int(_configured_pages))
    if DEFAULT_TOTAL_PUZZLES > DEFAULT_PAGES * PUZZLES_PER_PAGE:
        DEFAULT_PAGES = math.ceil(DEFAULT_TOTAL_PUZZLES / PUZZLES_PER_PAGE)

DEFAULT_TARGET_SCORE = float(PDF_CONFIG.get("default_target_score", 30.0))
DEFAULT_TIME_BUDGET = float(PDF_CONFIG.get("default_time_budget", 40.0))
DEFAULT_MARGIN_CM = float(PAGE_CONFIG.get("margin_cm", 4.0))
DEFAULT_GAP_CM = float(PAGE_CONFIG.get("gap_cm", 2.0))
PAGE_WIDTH_CM = float(PAGE_CONFIG.get("width_cm", 29.7))
PAGE_HEIGHT_CM = float(PAGE_CONFIG.get("height_cm", 21.0))
FOOTER_OFFSET_CM = float(PAGE_CONFIG.get("footer_offset_cm", 1.0))
FONT_SCALE = float(RENDER_CONFIG.get("font_scale_factor", 0.65))
OUTPUT_PREFIX = str(OUTPUT_CONFIG.get("filename_prefix", "sudoku_9x9_pack"))
FALLBACK_SEED_MULTIPLIER = int(FALLBACK_CONFIG.get("seed_multiplier", 7))
FALLBACK_REDUCE_SHARE = float(FALLBACK_CONFIG.get("reduce_time_share", 0.5))
FALLBACK_MIN_TIME = float(FALLBACK_CONFIG.get("min_time_budget", 2.0))
DEFAULT_PUZZLE_KIND = _default_puzzle_kind()

SCRIPT_DIR = Path(__file__).resolve().parent
PUZZLE_ROOT = SCRIPT_DIR.parent.parent
INCH_PER_CM = 0.3937007874

_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 62>>stream\nBT /F1 12 Tf 36 120 Td (Sudoku Export Placeholder) Tj ET\nendstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n"
    b"0000000123 00000 n \n0000000256 00000 n \n0000000379 00000 n \n"
    b"trailer<</Root 1 0 R/Size 6>>\nstartxref\n436\n%%EOF\n"
)


def _import_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for module '{name}' from path '{path}'")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _resolve_output_path(out: Optional[str]) -> Path:
    if out:
        return Path(out)
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"{OUTPUT_PREFIX}_{timestamp}.pdf")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a Sudoku PDF pack using project configuration.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output PDF path. If not set, a timestamped name is generated automatically.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Base seed for reproducibility. If not set, the current timestamp is used.",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=DEFAULT_TARGET_SCORE,
        help="Target interest score per puzzle (default from config).",
    )
    parser.add_argument(
        "--time",
        type=float,
        default=DEFAULT_TIME_BUDGET,
        help="Time budget per puzzle in seconds (default from config).",
    )
    parser.add_argument(
        "--margin-cm",
        type=float,
        default=DEFAULT_MARGIN_CM,
        help="Margin around the page in centimetres (default from config).",
    )
    parser.add_argument(
        "--gap-cm",
        type=float,
        default=DEFAULT_GAP_CM,
        help="Gap between puzzles in centimetres (default from config).",
    )
    parser.add_argument(
        "--puzzle",
        default=DEFAULT_PUZZLE_KIND,
        help="Puzzle kind to operate on (default from config).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    puzzle_kind = str(args.puzzle)
    if puzzle_kind != "sudoku-9x9":
        raise SystemExit("Only 'sudoku-9x9' puzzle kind is supported by this script.")

    base_seed = args.seed if args.seed is not None else int(time.time())
    out_path = _resolve_output_path(args.out)

    gen_path = PUZZLE_ROOT / "generator" / "legacy" / "__init__.py"
    sol_path = PUZZLE_ROOT / "solver" / "legacy" / "__init__.py"
    if not gen_path.exists() or not sol_path.exists():
        raise SystemExit(
            "Legacy generator/solver modules are missing from the puzzle package layout."
        )

    generator = _import_module_from(gen_path, "puzzle_sudoku_9x9_generator_legacy")

    solver_spec = _build_solver_spec(puzzle_kind)
    solver_profile = "dev"
    solver_module_info = None

    def _verify_solution(solution_grid, index: int) -> None:
        nonlocal solver_module_info

        grid_str = generator.to_string(solution_grid)
        payload, resolved = solver_port.check_uniqueness(
            puzzle_kind,
            dict(solver_spec),
            {"grid": grid_str, "artifact_id": f"inline-solution-{index + 1}"},
            profile=solver_profile,
        )

        if solver_module_info is None:
            solver_module_info = resolved
            print(
                f"  -> Uniqueness via solver '{resolved.impl_id}' (state={resolved.state})"
            )

        if not payload.get("unique", False):
            raise RuntimeError(
                f"Uniqueness check failed for puzzle {index + 1} using solver '{resolved.impl_id}'"
            )

    total_puzzles = max(1, DEFAULT_TOTAL_PUZZLES)
    puzzles_per_page = PUZZLES_PER_PAGE
    pages = max(1, math.ceil(total_puzzles / puzzles_per_page))

    print(f"Generating {total_puzzles} '{puzzle_kind}' puzzles with base seed: {base_seed}")
    puzzles, solutions, scores, reports = [], [], [], []

    for i in range(total_puzzles):
        print(f"Generating puzzle {i + 1}/{total_puzzles}...")
        res = generator.generate_interesting(
            seed=base_seed + i,
            target_score=args.target,
            time_budget=args.time,
        )
        if res is None:
            print(f"  -> Fallback for puzzle {i + 1}")
            sol = generator.generate_full_solution(seed=base_seed * FALLBACK_SEED_MULTIPLIER + i)
            rng = random.Random(base_seed + i)
            fallback_budget = max(FALLBACK_MIN_TIME, args.time * FALLBACK_REDUCE_SHARE)
            pzl, stp, sc, rep = generator.reduce_with_checks(
                sol,
                target_score=0.0,
                rng=rng,
                time_budget=fallback_budget,
            )
            _verify_solution(sol, i)
            puzzles.append(pzl)
            solutions.append(sol)
            scores.append(sc)
            reports.append(rep)
            continue

        pzl, sol, sc, rep, stp = res
        _verify_solution(sol, i)
        puzzles.append(pzl)
        solutions.append(sol)
        scores.append(sc)
        reports.append(rep)
        print(f"  -> Done. Score: {sc:.1f}")

    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt

    page_w_in = PAGE_WIDTH_CM * INCH_PER_CM
    page_h_in = PAGE_HEIGHT_CM * INCH_PER_CM
    margin_in = args.margin_cm * INCH_PER_CM
    gap_in = args.gap_cm * INCH_PER_CM

    avail_w = page_w_in - 2 * margin_in - gap_in * (LAYOUT_COLS - 1)
    avail_h = page_h_in - 2 * margin_in - gap_in * (LAYOUT_ROWS - 1)
    grid_size = min(avail_w / max(1, LAYOUT_COLS), avail_h / max(1, LAYOUT_ROWS))

    def draw_grid(ax, puzzle, left_in, bottom_in, size_in):
        ax.set_position([left_in / page_w_in, bottom_in / page_h_in, size_in / page_w_in, size_in / page_h_in])
        ax.tick_params(axis="both", which="both", bottom=False, top=False, left=False, right=False,
                       labelbottom=False, labelleft=False)
        for idx in range(10):
            linewidth = 1.5 if idx % 3 else 3.0
            ax.axvline(idx / 9, color="k", linewidth=linewidth)
            ax.axhline(idx / 9, color="k", linewidth=linewidth)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        font_size = max(1, int(FONT_SCALE * size_in * 72 / 9))
        for r in range(9):
            for c in range(9):
                value = puzzle[r][c]
                if value:
                    x = (c + 0.5) / 9
                    y = 1 - (r + 0.5) / 9
                    ax.text(x, y, str(value), ha="center", va="center", fontsize=font_size)

    footer_y_pos_norm = (FOOTER_OFFSET_CM * INCH_PER_CM) / page_h_in

    with PdfPages(out_path) as pdf:
        for page_num in range(pages):
            fig = plt.figure(figsize=(page_w_in, page_h_in))
            start_idx = page_num * puzzles_per_page
            page_puzzles = puzzles[start_idx:start_idx + puzzles_per_page]
            page_scores = scores[start_idx:start_idx + puzzles_per_page]

            idx_on_page = 0
            for row in range(LAYOUT_ROWS):
                bottom = margin_in + (LAYOUT_ROWS - 1 - row) * (grid_size + gap_in)
                for col in range(LAYOUT_COLS):
                    if idx_on_page >= len(page_puzzles):
                        break
                    left = margin_in + col * (grid_size + gap_in)
                    ax = fig.add_axes([0, 0, 1, 1], frameon=False)
                    draw_grid(ax, page_puzzles[idx_on_page], left, bottom, grid_size)
                    idx_on_page += 1
                if idx_on_page >= len(page_puzzles):
                    break

            if page_scores:
                score_text = ", ".join(f"{s:.1f}" for s in page_scores)
            else:
                score_text = "—"
            footer_text = (
                f"Сложность (Interest Score): {score_text}    "
                f"Time budget = {args.time}   Target Score = {args.target}"
            )
            fig.text(0.5, footer_y_pos_norm, footer_text, ha="center", va="bottom", fontsize=8)

            pdf.savefig(fig)
            plt.close(fig)

    print(f"\nPDF with {pages} pages and {len(puzzles)} puzzles saved to: {out_path.resolve()}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

def port_export(bundle: Dict[str, Any], *, output_dir: str) -> Dict[str, Any]:
    """Render a minimal PDF bundle and return output metadata.

    The port has no side effects outside of writing the resulting PDF file inside
    ``output_dir`` relative to the project root. The returned dictionary contains
    the relative path to the generated file and a dummy timing metric.
    """
    if not isinstance(bundle, dict):
        raise TypeError("bundle must be a mapping")

    inputs = bundle.get("inputs")
    target = bundle.get("target")
    render_meta = bundle.get("render_meta")
    if not (isinstance(inputs, dict) and isinstance(target, dict) and isinstance(render_meta, dict)):
        raise ValueError("bundle must include inputs, target and render_meta")

    complete_ref = inputs.get("complete_ref")
    verdict_ref = inputs.get("verdict_ref")
    if not (isinstance(complete_ref, str) and complete_ref.startswith("sha256-")):
        raise ValueError("inputs.complete_ref must be a sha256 reference")
    if not (isinstance(verdict_ref, str) and verdict_ref.startswith("sha256-")):
        raise ValueError("inputs.verdict_ref must be a sha256 reference")

    if target.get("format") != "pdf":
        raise ValueError("target.format must be 'pdf'")
    template = target.get("template")
    if not isinstance(template, str) or not template:
        raise ValueError("target.template must be a non-empty string")

    if "dpi" not in render_meta or "page" not in render_meta:
        raise ValueError("render_meta must provide dpi and page")

    # Ensure referenced artifacts exist in the store.
    artifact_store.load_artifact(complete_ref)
    artifact_store.load_artifact(verdict_ref)

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = Path(output_dir)
    if out_dir.is_absolute():
        raise ValueError("output_dir must be a relative path inside the project")

    target_dir = (repo_root / out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{complete_ref[7:15]}-{verdict_ref[7:15]}.pdf"
    pdf_path = target_dir / filename
    if not pdf_path.exists():
        pdf_path.write_bytes(_MINIMAL_PDF)

    relative_path = (out_dir / filename).as_posix()
    return {"pdf_path": relative_path, "time_ms": 0}
