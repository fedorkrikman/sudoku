import importlib.util
import sys
import os
import random

# Путь именно к файлу в текущем каталоге, рядом с тестом
here = os.path.dirname(os.path.abspath(__file__))
gen_path = os.path.join(here, "sudoku_generator.py")

spec = importlib.util.spec_from_file_location("sg", gen_path)
sg = importlib.util.module_from_spec(spec)
sys.modules["sg"] = sg
spec.loader.exec_module(sg)

def valid(grid):
    need = list(range(1, 10))
    rows = all(sorted(r) == need for r in grid)
    cols = all(sorted(c) == need for c in zip(*grid))
    box = lambda br, bc: [grid[r][c] for r in range(br, br+3) for c in range(bc, bc+3)]
    boxes = all(sorted(box(r, c)) == need for r in (0, 3, 6) for c in (0, 3, 6))
    return rows and cols and boxes

def run(n=20):
    for i in range(n):
        g = sg.generate_full_solution(seed=random.randrange(1 << 30))
        assert valid(g), f"invalid at i={i}"
    print(f"OK: {n} full solutions valid")

if __name__ == "__main__":
    run()
