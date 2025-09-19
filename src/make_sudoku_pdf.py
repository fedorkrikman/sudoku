#!/usr/bin/env python3
"""
make_sudoku_pdf.py
Create a landscape A4 PDF with 8 Sudoku puzzles (2 pages, 2x2 per page),
with configurable margins and spacing.
Uses sudoku_generator.py (which uses sudoku_solver.py) located in the same directory by default.

Usage (from the same folder):
  python make_sudoku_pdf.py

Or with custom parameters:
  python make_sudoku_pdf.py --out my_puzzles.pdf --seed 12345 --target 35 --time 20
"""

import argparse
import importlib.util
import sys
import time
import datetime
from pathlib import Path

# --- CLI ---
parser = argparse.ArgumentParser(description="Generate an 8-pack Sudoku PDF (2 pages, landscape A4).")
parser.add_argument("--out", default=None, help="Output PDF path. If not set, a name with a timestamp is generated automatically.")
parser.add_argument("--seed", type=int, default=None, help="Base seed for reproducibility. If not set, a random seed is used.")
parser.add_argument("--target", type=float, default=30.0, help="Target interest score per puzzle (default: 30.0)")
parser.add_argument("--time", type=float, default=40.0, help="Time budget per puzzle, seconds (default: 40.0)")
parser.add_argument("--margin-cm", type=float, default=4.0, help="Margin around page in cm (default: 4.0)")
parser.add_argument("--gap-cm", type=float, default=2.0, help="Gap between puzzles in cm (default: 2.0)")
args = parser.parse_args()

# --- Handle automatic seed and output path ---
base_seed = args.seed if args.seed is not None else int(time.time())

if args.out:
    out_path = Path(args.out)
else:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(f"sudoku_9x9_pack_{timestamp}.pdf")

here = Path(__file__).resolve().parent

# --- Import generator ---
def import_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for module '{name}' from path '{path}'")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

gen_path = here / "sudoku_generator.py"
sol_path = here / "sudoku_solver.py"
if not gen_path.exists() or not sol_path.exists():
    raise SystemExit("Expected sudoku_generator.py and sudoku_solver.py in the same folder.")

genmod = import_module_from(gen_path, "sudoku_generator")

# --- Make 8 puzzles ---
print(f"Generating 8 puzzles with base seed: {base_seed}")
puzzles, solutions, scores, reports = [], [], [], []

# Generate 8 puzzles for two pages
for i in range(8):
    print(f"Generating puzzle {i+1}/8...")
    res = genmod.generate_interesting(seed=base_seed+i, target_score=args.target, time_budget=args.time)
    if res is None:
        # fallback strategy
        print(f"  -> Fallback for puzzle {i+1}")
        sol = genmod.generate_full_solution(seed=base_seed*7+i)
        pzl, stp, sc, rep = genmod.reduce_with_checks(sol, target_score=0.0, rng=__import__('random').Random(base_seed+i), time_budget=max(2.0, args.time/2))
        puzzles.append(pzl); solutions.append(sol); scores.append(sc); reports.append(rep)
        continue
    pzl, sol, sc, rep, stp = res
    puzzles.append(pzl); solutions.append(sol); scores.append(sc); reports.append(rep)
    print(f"  -> Done. Score: {sc:.1f}")

# --- PDF rendering ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

inch_per_cm = 0.3937007874
page_w_in = 29.7 * inch_per_cm  # A4 landscape width
page_h_in = 21.0 * inch_per_cm  # A4 landscape height
margin_in = args.margin_cm * inch_per_cm
gap_in = args.gap_cm * inch_per_cm

avail_w = page_w_in - 2*margin_in - gap_in
avail_h = page_h_in - 2*margin_in - gap_in
grid_size = min(avail_w/2.0, avail_h/2.0)

def draw_grid(ax, puzzle, left_in, bottom_in, size_in):
    ax.set_position([left_in/page_w_in, bottom_in/page_h_in, size_in/page_w_in, size_in/page_h_in])
    ax.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False, labelbottom=False, labelleft=False)
    for i in range(10):
        lw = 1.5 if i % 3 else 3.0
        ax.axvline(i/9, color='k', linewidth=lw)
        ax.axhline(i/9, color='k', linewidth=lw)
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off')
    fs = int(0.65 * size_in * 72 / 9)  # font size scaled to grid
    for r in range(9):
        for c in range(9):
            v = puzzle[r][c]
            if v:
                x = (c + 0.5)/9
                y = 1 - (r + 0.5)/9
                ax.text(x, y, str(v), ha='center', va='center', fontsize=fs)

lefts = [margin_in, margin_in + grid_size + gap_in]
bottoms = [margin_in + grid_size + gap_in, margin_in]

# Y position for footer text, 1cm from bottom edge
footer_y_pos_norm = (1.0 * inch_per_cm) / page_h_in

with PdfPages(out_path) as pdf:
    # Loop to create two pages
    for page_num in range(2):
        fig = plt.figure(figsize=(page_w_in, page_h_in))
        
        # Get puzzles and scores for the current page
        start_idx = page_num * 4
        page_puzzles = puzzles[start_idx : start_idx + 4]
        page_scores = scores[start_idx : start_idx + 4]

        axes = [fig.add_axes([0,0,1,1], frameon=False) for _ in range(4)]
        
        idx_on_page = 0
        for row in range(2):
            for col in range(2):
                draw_grid(axes[idx_on_page], page_puzzles[idx_on_page], lefts[col], bottoms[row], grid_size)
                idx_on_page += 1
        
        # Add footer with score and proper spacing
        footer_text = f"Сложность (Interest Score): {', '.join(f'{s:.1f}' for s in page_scores)}    Time budget = {args.time}      Target Score = {args.target}"
        fig.text(0.5, footer_y_pos_norm, footer_text, ha='center', va='bottom', fontsize=8)
        
        pdf.savefig(fig)
        plt.close(fig)

print(f"\nPDF with 2 pages and 8 puzzles saved to: {out_path.resolve()}")