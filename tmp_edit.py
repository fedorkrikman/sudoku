from pathlib import Path

path = Path("src/make_sudoku_pdf.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
for i, line in enumerate(lines):
    if "pzl, stp, sc, rep =" in line:
        lines[i] = line.replace("pzl, stp, sc, rep =", "pzl, _, sc, rep =")
    if "footer_text = f" in line and "Interest Score" in line:
        lines[i] = "        footer_text = f\"Scores (Interest Score): {', '.join(f'{s:.1f}' for s in page_scores)}    Time budget = {args.time}      Target Score = {args.target}\"\r\n"
path.write_text("".join(lines), encoding="utf-8")
