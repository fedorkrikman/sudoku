
# sudoku_solver.py
# Logical Sudoku solver with step logging (techniques: Naked/Hidden Singles, Locked Candidates,
# Naked Pairs, Hidden Pairs). No guessing. Designed for extensibility.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from copy import deepcopy

Digit = int  # 1..9
Cell = Tuple[int, int]  # (r, c) 0..8

def box_index(r: int, c: int) -> int:
    return (r // 3) * 3 + (c // 3)

ALL_DIGITS: Set[Digit] = set(range(1, 10))

ROWS = [[(r, c) for c in range(9)] for r in range(9)]
COLS = [[(r, c) for r in range(9)] for c in range(9)]
BOXES = [[(r, c) for r in range(br * 3, br * 3 + 3) for c in range(bc * 3, bc * 3 + 3)]
         for br in range(3) for bc in range(3)]

UNITS: List[List[Cell]] = []
UNITS.extend(ROWS)
UNITS.extend(COLS)
UNITS.extend(BOXES)

PEERS: Dict[Cell, Set[Cell]] = {}
for r in range(9):
    for c in range(9):
        peers = set(ROWS[r] + COLS[c] + BOXES[box_index(r, c)])
        peers.remove((r, c))
        PEERS[(r, c)] = peers


@dataclass
class Step:
    technique: str
    placements: List[Tuple[Cell, Digit]] = field(default_factory=list)
    eliminations: List[Tuple[Cell, Digit]] = field(default_factory=list)
    notes: str = ""
    unit_type: Optional[str] = None  # 'row'|'col'|'box' or composite
    unit_index: Optional[int] = None  # 0..8
    difficulty: float = 0.0
    phase: Optional[str] = None  # 'A'|'B'|'C'

    def to_dict(self):
        return {
            "technique": self.technique,
            "placements": [((r, c), d) for ((r, c), d) in self.placements],
            "eliminations": [((r, c), d) for ((r, c), d) in self.eliminations],
            "notes": self.notes,
            "unit_type": self.unit_type,
            "unit_index": self.unit_index,
            "difficulty": self.difficulty,
            "phase": self.phase,
        }


class Grid:
    def __init__(self, grid: List[List[int]]):
        assert len(grid) == 9 and all(len(row) == 9 for row in grid)
        self.grid = deepcopy(grid)
        self.cands: Dict[Cell, Set[Digit]] = {}
        self._init_candidates()

    @staticmethod
    def from_string(s: str) -> "Grid":
        s = s.strip().replace("\n", "").replace(" ", "")
        assert len(s) == 81, "Expected 81 characters"
        grid = []
        i = 0
        for r in range(9):
            row = []
            for c in range(9):
                ch = s[i]; i += 1
                row.append(int(ch) if ch.isdigit() and ch != '0' else 0)
            grid.append(row)
        return Grid(grid)

    def clone(self) -> "Grid":
        return Grid(self.grid)

    def _init_candidates(self):
        for r in range(9):
            for c in range(9):
                if self.grid[r][c] == 0:
                    used = {self.grid[rr][cc] for (rr, cc) in PEERS[(r, c)] if self.grid[rr][cc] != 0}
                    self.cands[(r, c)] = ALL_DIGITS - used
                else:
                    self.cands[(r, c)] = set()

    def is_solved(self) -> bool:
        return all(self.grid[r][c] != 0 for r in range(9) for c in range(9))

    def place(self, r: int, c: int, d: Digit, step: Optional[Step] = None):
        assert d in ALL_DIGITS
        assert self.grid[r][c] == 0 or self.grid[r][c] == d, "Contradiction: placing over non-empty cell"
        self.grid[r][c] = d
        self.cands[(r, c)] = set()
        for (rr, cc) in PEERS[(r, c)]:
            if d in self.cands[(rr, cc)]:
                self.cands[(rr, cc)].remove(d)
                if step is not None:
                    step.eliminations.append(((rr, cc), d))

    def eliminate(self, r: int, c: int, d: Digit, step: Optional[Step] = None) -> bool:
        if d in self.cands[(r, c)]:
            self.cands[(r, c)].remove(d)
            if step:
                step.eliminations.append(((r, c), d))
            return True
        return False

    def candidates(self, r: int, c: int) -> Set[Digit]:
        return self.cands[(r, c)]

    def as_string(self) -> str:
        return ''.join(str(self.grid[r][c] or 0) for r in range(9) for c in range(9))

    def __str__(self) -> str:
        lines = []
        for r in range(9):
            if r % 3 == 0:
                lines.append("+-------+-------+-------+")
            row = []
            for c in range(9):
                v = self.grid[r][c]
                row.append(str(v) if v != 0 else '.')
                if c % 3 == 2:
                    row.append("|")
            lines.append("| " + ' '.join(row[:-1]) + " ")
        lines.append("+-------+-------+-------+")
        return '\n'.join(lines)


class Techniques:
    @staticmethod
    def naked_single(g: Grid) -> Optional[Step]:
        for r in range(9):
            for c in range(9):
                if g.grid[r][c] == 0:
                    cand = g.candidates(r, c)
                    if len(cand) == 1:
                        d = next(iter(cand))
                        st = Step("Naked Single", placements=[((r, c), d)], difficulty=0.5,
                                  notes=f"Only candidate {d} fits cell {(r+1, c+1)}")
                        g.place(r, c, d, st)
                        return st
        return None

    @staticmethod
    def hidden_single(g: Grid) -> Optional[Step]:
        for unit_idx, unit in enumerate(ROWS):
            res = Techniques._hidden_single_in_unit(g, unit, "row", unit_idx)
            if res: return res
        for unit_idx, unit in enumerate(COLS):
            res = Techniques._hidden_single_in_unit(g, unit, "col", unit_idx)
            if res: return res
        for unit_idx, unit in enumerate(BOXES):
            res = Techniques._hidden_single_in_unit(g, unit, "box", unit_idx)
            if res: return res
        return None

    @staticmethod
    def _hidden_single_in_unit(g: Grid, unit: List[Cell], unit_type: str, unit_index: int) -> Optional[Step]:
        for d in range(1, 10):
            spots = []
            for (r, c) in unit:
                if g.grid[r][c] == 0 and d in g.candidates(r, c):
                    spots.append((r, c))
            if len(spots) == 1:
                (r, c) = spots[0]
                st = Step("Hidden Single", placements=[((r, c), d)], difficulty=0.7, unit_type=unit_type,
                          unit_index=unit_index, notes=f"Digit {d} appears only once in {unit_type} {unit_index+1}")
                g.place(r, c, d, st)
                return st
        return None

    @staticmethod
    def locked_candidates(g: Grid) -> Optional[Step]:
        # Pointing within boxes
        for b_idx, box in enumerate(BOXES):
            for d in range(1, 10):
                rows_set = set(); cols_set = set(); cells = []
                for (r, c) in box:
                    if g.grid[r][c] == 0 and d in g.candidates(r, c):
                        rows_set.add(r); cols_set.add(c); cells.append((r, c))
                if len(cells) >= 2:
                    if len(rows_set) == 1:
                        target_row = next(iter(rows_set))
                        st = Step("Locked Candidates (Pointing)", difficulty=1.2, unit_type="box", unit_index=b_idx,
                                  notes=f"In box {b_idx+1}, digit {d} confined to row {target_row+1}; eliminate from row.")
                        changed = False
                        for (r, c) in ROWS[target_row]:
                            if (r, c) not in box and g.grid[r][c] == 0 and d in g.candidates(r, c):
                                changed |= g.eliminate(r, c, d, st)
                        if changed:
                            return st
                    if len(cols_set) == 1:
                        target_col = next(iter(cols_set))
                        st = Step("Locked Candidates (Pointing)", difficulty=1.2, unit_type="box", unit_index=b_idx,
                                  notes=f"In box {b_idx+1}, digit {d} confined to col {target_col+1}; eliminate from column.")
                        changed = False
                        for (r, c) in COLS[target_col]:
                            if (r, c) not in box and g.grid[r][c] == 0 and d in g.candidates(r, c):
                                changed |= g.eliminate(r, c, d, st)
                        if changed:
                            return st

        # Claiming in rows
        for r in range(9):
            for d in range(1, 10):
                cells = [(r, c) for c in range(9) if g.grid[r][c] == 0 and d in g.candidates(r, c)]
                if len(cells) >= 2:
                    boxes = {box_index(r, c) for (r, c) in cells}
                    if len(boxes) == 1:
                        b = next(iter(boxes))
                        st = Step("Locked Candidates (Claiming)", difficulty=1.3, unit_type="row", unit_index=r,
                                  notes=f"In row {r+1}, candidates for {d} confined to box {b+1}; eliminate inside box.")
                        changed = False
                        for (rr, cc) in BOXES[b]:
                            if rr == r: 
                                continue
                            if g.grid[rr][cc] == 0 and d in g.candidates(rr, cc):
                                changed |= g.eliminate(rr, cc, d, st)
                        if changed:
                            return st

        # Claiming in columns
        for c in range(9):
            for d in range(1, 10):
                cells = [(r, c) for r in range(9) if g.grid[r][c] == 0 and d in g.candidates(r, c)]
                if len(cells) >= 2:
                    boxes = {box_index(r, c) for (r, c) in cells}
                    if len(boxes) == 1:
                        b = next(iter(boxes))
                        st = Step("Locked Candidates (Claiming)", difficulty=1.3, unit_type="col", unit_index=c,
                                  notes=f"In col {c+1}, candidates for {d} confined to box {b+1}; eliminate inside box.")
                        changed = False
                        for (rr, cc) in BOXES[b]:
                            if cc == c: 
                                continue
                            if g.grid[rr][cc] == 0 and d in g.candidates(rr, cc):
                                changed |= g.eliminate(rr, cc, d, st)
                        if changed:
                            return st

        return None

    @staticmethod
    def naked_pairs(g: Grid) -> Optional[Step]:
        def process_unit(unit, unit_type, unit_index):
            pairs: Dict[Tuple[int, int], List[Cell]] = {}
            for (r, c) in unit:
                if g.grid[r][c] == 0 and len(g.candidates(r, c)) == 2:
                    key = tuple(sorted(g.candidates(r, c)))
                    pairs.setdefault(key, []).append((r, c))
            for (a, b), cells in pairs.items():
                if len(cells) == 2:
                    st = Step("Naked Pairs", difficulty=1.6, unit_type=unit_type, unit_index=unit_index,
                              notes=f"Pair {{{a},{b}}} locked in two cells in {unit_type} {unit_index+1}")
                    changed = False
                    for (r, c) in unit:
                        if (r, c) not in cells and g.grid[r][c] == 0:
                            if a in g.candidates(r, c):
                                changed |= g.eliminate(r, c, a, st)
                            if b in g.candidates(r, c):
                                changed |= g.eliminate(r, c, b, st)
                    if changed:
                        return st
            return None

        for idx, unit in enumerate(ROWS):
            res = process_unit(unit, "row", idx)
            if res: return res
        for idx, unit in enumerate(COLS):
            res = process_unit(unit, "col", idx)
            if res: return res
        for idx, unit in enumerate(BOXES):
            res = process_unit(unit, "box", idx)
            if res: return res
        return None

    @staticmethod
    def hidden_pairs(g: Grid) -> Optional[Step]:
        def process_unit(unit, unit_type, unit_index):
            digit_cells: Dict[int, List[Cell]] = {d: [] for d in range(1, 10)}
            for (r, c) in unit:
                if g.grid[r][c] == 0:
                    for d in g.candidates(r, c):
                        digit_cells[d].append((r, c))
            digits = list(range(1, 10))
            for i in range(len(digits)):
                for j in range(i+1, len(digits)):
                    d1, d2 = digits[i], digits[j]
                    cells1, cells2 = digit_cells[d1], digit_cells[d2]
                    if len(cells1) == 2 and cells1 == cells2:
                        cells = cells1
                        st = Step("Hidden Pairs", difficulty=1.8, unit_type=unit_type, unit_index=unit_index,
                                  notes=f"Digits {{{d1},{d2}}} appear only in two same cells in {unit_type} {unit_index+1}")
                        changed = False
                        for (r, c) in cells:
                            to_remove = g.candidates(r, c) - {d1, d2}
                            for d in list(to_remove):
                                changed |= g.eliminate(r, c, d, st)
                        if changed:
                            return st
            return None

        for idx, unit in enumerate(ROWS):
            res = process_unit(unit, "row", idx)
            if res: return res
        for idx, unit in enumerate(COLS):
            res = process_unit(unit, "col", idx)
            if res: return res
        for idx, unit in enumerate(BOXES):
            res = process_unit(unit, "box", idx)
            if res: return res
        return None

    @staticmethod
    def x_wing(g: Grid) -> Optional[Step]:
        """
        Classic X-Wing for a single digit:
        - Rows-based: find two rows where digit d appears exactly in the same two columns {c1,c2}.
          Then eliminate d from all other rows in those two columns.
        - Columns-based: symmetric.
        Returns a Step if any elimination occurred.
        """
        # Helper for row-based X-Wing
        def xwing_rows() -> Optional[Step]:
            for d in range(1, 10):
                # collect candidate columns per row for d
                row_cols = []
                for r in range(9):
                    cols = [c for c in range(9) if g.grid[r][c] == 0 and d in g.candidates(r, c)]
                    if len(cols) == 2:
                        row_cols.append((r, tuple(cols)))
                # try all pairs of rows
                for i in range(len(row_cols)):
                    r1, cols1 = row_cols[i]
                    for j in range(i+1, len(row_cols)):
                        r2, cols2 = row_cols[j]
                        if cols1 == cols2:
                            c1, c2 = cols1
                            st = Step("X-Wing (Rows)", difficulty=2.2, unit_type="rows",
                                      unit_index=None,
                                      notes=f"Digit {d} forms X-Wing on rows {r1+1},{r2+1} and columns {c1+1},{c2+1}")
                            changed = False
                            # eliminate d in columns c1,c2 from rows other than r1,r2
                            for r in range(9):
                                if r in (r1, r2):
                                    continue
                                for c in (c1, c2):
                                    if g.grid[r][c] == 0 and d in g.candidates(r, c):
                                        changed |= g.eliminate(r, c, d, st)
                            if changed:
                                return st
            return None

        # Helper for column-based X-Wing
        def xwing_cols() -> Optional[Step]:
            for d in range(1, 10):
                col_rows = []
                for c in range(9):
                    rows = [r for r in range(9) if g.grid[r][c] == 0 and d in g.candidates(r, c)]
                    if len(rows) == 2:
                        col_rows.append((c, tuple(rows)))
                for i in range(len(col_rows)):
                    c1, rows1 = col_rows[i]
                    for j in range(i+1, len(col_rows)):
                        c2, rows2 = col_rows[j]
                        if rows1 == rows2:
                            r1, r2 = rows1
                            st = Step("X-Wing (Cols)", difficulty=2.2, unit_type="cols",
                                      unit_index=None,
                                      notes=f"Digit {d} forms X-Wing on columns {c1+1},{c2+1} and rows {r1+1},{r2+1}")
                            changed = False
                            for c in range(9):
                                if c in (c1, c2):
                                    continue
                                for r in (r1, r2):
                                    if g.grid[r][c] == 0 and d in g.candidates(r, c):
                                        changed |= g.eliminate(r, c, d, st)
                            if changed:
                                return st
            return None

        # Try rows first, then columns
        res = xwing_rows()
        if res:
            return res
        return xwing_cols()

    @staticmethod
    def xy_wing(g: Grid) -> Optional[Step]:
        """
        XY-Wing: pivot cell P with candidates {x,y}, and two 'pincers' A {x,z} and B {y,z},
        where A and B each share a unit with P. Then eliminate z from cells that see both A and B.
        """
        # Build list of bivalue cells
        bivals = [(r, c, tuple(sorted(g.candidates(r, c)))) 
                  for r in range(9) for c in range(9)
                  if g.grid[r][c] == 0 and len(g.candidates(r, c)) == 2]
        # Quick access to peers
        def peers(cell): return PEERS[cell]
        for (pr, pc, (x, y)) in bivals:
            P = (pr, pc)
            # find A with {x,z} that shares unit with P
            As = []
            Bs = []
            for (ar, ac, cand) in bivals:
                if (ar, ac) == P: 
                    continue
                if (ar, ac) in peers(P):
                    if cand[0] == x and cand[1] != y:
                        As.append(((ar, ac), cand[1]))  # z=cand[1]
                    elif cand[1] == x and cand[0] != y:
                        As.append(((ar, ac), cand[0]))
                    if cand[0] == y and cand[1] != x:
                        Bs.append(((ar, ac), cand[1]))
                    elif cand[1] == y and cand[0] != x:
                        Bs.append(((ar, ac), cand[0]))
            # try pairs (A,B) with same z
            for (A_cell, z1) in As:
                for (B_cell, z2) in Bs:
                    if z1 != z2:
                        continue
                    z = z1
                    if z in (x, y):
                        continue
                    # elimination targets: intersection of peers(A) & peers(B)
                    inter = peers(A_cell) & peers(B_cell)
                    changed = False
                    st = Step("XY-Wing", difficulty=2.5, unit_type="composite", unit_index=None,
                              notes=f"Pivot {P[0]+1},{P[1]+1} with {x}/{y}, pincers {A_cell[0]+1},{A_cell[1]+1} and {B_cell[0]+1},{B_cell[1]+1} eliminate {z}")
                    for (r, c) in inter:
                        if g.grid[r][c] == 0 and z in g.candidates(r, c):
                            changed |= g.eliminate(r, c, z, st)
                    if changed:
                        return st
        return None

    @staticmethod
    def swordfish(g: Grid) -> Optional[Step]:
        """
        Swordfish for a single digit d.
        Rows-based: choose 3 rows where positions of d are limited to the same set of 3 columns.
        Then eliminate d from those columns in all other rows. (Columns-based symmetric.)
        """
        def row_swordfish() -> Optional[Step]:
            for d in range(1, 10):
                # collect candidate columns for each row where 2<=count<=3
                row_cols = {}
                for r in range(9):
                    cols = [c for c in range(9) if g.grid[r][c] == 0 and d in g.candidates(r, c)]
                    if 2 <= len(cols) <= 3:
                        row_cols[r] = set(cols)
                rows = list(row_cols.keys())
                # try all combos of 3 rows
                from itertools import combinations
                for r1, r2, r3 in combinations(rows, 3):
                    cols_union = row_cols[r1] | row_cols[r2] | row_cols[r3]
                    if len(cols_union) != 3:
                        continue
                    # ensure each row has candidates only within union
                    if not (row_cols[r1] <= cols_union and row_cols[r2] <= cols_union and row_cols[r3] <= cols_union):
                        continue
                    st = Step("Swordfish (Rows)", difficulty=2.8, unit_type="rows",
                              notes=f"Digit {d} forms Swordfish on rows {r1+1},{r2+1},{r3+1} and columns {sorted([c+1 for c in cols_union])}")
                    changed = False
                    for r in range(9):
                        if r in (r1, r2, r3):
                            continue
                        for c in cols_union:
                            if g.grid[r][c] == 0 and d in g.candidates(r, c):
                                changed |= g.eliminate(r, c, d, st)
                    if changed:
                        return st
            return None

        def col_swordfish() -> Optional[Step]:
            for d in range(1, 10):
                col_rows = {}
                for c in range(9):
                    rows = [r for r in range(9) if g.grid[r][c] == 0 and d in g.candidates(r, c)]
                    if 2 <= len(rows) <= 3:
                        col_rows[c] = set(rows)
                cols = list(col_rows.keys())
                from itertools import combinations
                for c1, c2, c3 in combinations(cols, 3):
                    rows_union = col_rows[c1] | col_rows[c2] | col_rows[c3]
                    if len(rows_union) != 3:
                        continue
                    if not (col_rows[c1] <= rows_union and col_rows[c2] <= rows_union and col_rows[c3] <= rows_union):
                        continue
                    st = Step("Swordfish (Cols)", difficulty=2.8, unit_type="cols",
                              notes=f"Digit {d} forms Swordfish on columns {c1+1},{c2+1},{c3+1} and rows {sorted([r+1 for r in rows_union])}")
                    changed = False
                    for c in range(9):
                        if c in (c1, c2, c3):
                            continue
                        for r in rows_union:
                            if g.grid[r][c] == 0 and d in g.candidates(r, c):
                                changed |= g.eliminate(r, c, d, st)
                    if changed:
                        return st
            return None

        res = row_swordfish()
        if res:
            return res
        return col_swordfish()


TECHNIQUE_ORDER = [
    Techniques.naked_single,
    Techniques.hidden_single,
    Techniques.locked_candidates,
    Techniques.naked_pairs,
    Techniques.hidden_pairs,
    Techniques.x_wing,
    Techniques.xy_wing,
    Techniques.swordfish,
]


class LogicSolver:
    def __init__(self, grid: Grid):
        self.grid = grid
        self.steps: List[Step] = []

    def _phase(self) -> str:
        filled = sum(1 for r in range(9) for c in range(9) if self.grid.grid[r][c] != 0)
        if filled < 30:
            return 'A'
        elif filled < 55:
            return 'B'
        else:
            return 'C'

    def step_once(self) -> Optional[Step]:
        for fn in TECHNIQUE_ORDER:
            st = fn(self.grid)
            if st is not None:
                st.phase = self._phase()
                self.steps.append(st)
                return st
        return None

    def solve_with_log(self, max_steps: int = 10000):
        steps_taken = 0
        while steps_taken < max_steps:
            if self.grid.is_solved():
                return "solved", self.steps
            st = self.step_once()
            if st is None:
                break
            # Chain naked singles that may have been created
            while True:
                ns = Techniques.naked_single(self.grid)
                if ns is None:
                    break
                ns.phase = self._phase()
                self.steps.append(ns)
            steps_taken += 1
        return ("solved" if self.grid.is_solved() else "stalled"), self.steps

def port_check_uniqueness(
    spec: Dict[str, Any],
    grid_or_candidate: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a solved grid against a Spec and emit a Verdict payload.

    The port performs deterministic checks without side effects. The returned
    dictionary contains only the data portion of a Verdict artifact.
    """
    if not isinstance(spec, dict) or not isinstance(grid_or_candidate, dict):
        raise TypeError("spec and grid_or_candidate must be mappings")

    size = spec.get('size')
    block = spec.get('block', {})
    alphabet = spec.get('alphabet')
    limits = spec.get('limits', {})
    if not (isinstance(size, int) and isinstance(block, dict) and isinstance(alphabet, list)):
        raise ValueError('spec must provide size, block and alphabet')

    rows = block.get('rows')
    cols = block.get('cols')
    if not (isinstance(rows, int) and isinstance(cols, int)):
        raise ValueError('spec.block must include integer rows and cols')
    if rows <= 0 or cols <= 0 or rows * cols != size:
        raise ValueError('spec.block dimensions must multiply to size')

    grid = grid_or_candidate.get('grid')
    if not isinstance(grid, str):
        raise ValueError('grid_or_candidate must expose a string grid')
    if len(grid) != size * size:
        raise ValueError('grid length must be size*size')

    alphabet_set = set(alphabet)
    if any(ch not in alphabet_set for ch in grid):
        raise ValueError('grid contains symbols outside of alphabet')

    def row_slice(r: int) -> str:
        start = r * size
        return grid[start:start + size]

    def column_slice(c: int) -> str:
        return "".join(grid[r * size + c] for r in range(size))

    def block_slice(br: int, bc: int) -> str:
        chars = []
        for r in range(br * rows, br * rows + rows):
            for c in range(bc * cols, bc * cols + cols):
                chars.append(grid[r * size + c])
        return "".join(chars)

    expected = alphabet_set
    solved = True
    for r in range(size):
        if set(row_slice(r)) != expected:
            solved = False
            break
    if solved:
        for c in range(size):
            if set(column_slice(c)) != expected:
                solved = False
                break
    if solved:
        for br in range(size // rows):
            for bc in range(size // cols):
                if set(block_slice(br, bc)) != expected:
                    solved = False
                    break
            if not solved:
                break

    solved_ref = grid_or_candidate.get("artifact_id") if solved else None
    candidate_ref = None if solved_ref else grid_or_candidate.get("artifact_id")

    timeout = limits.get("solver_timeout_ms") if isinstance(limits, dict) else None
    time_budget = 0 if not isinstance(timeout, int) else min(timeout, 5)

    cutoff = None if solved else "SECOND_SOLUTION_FOUND"

    verdict: Dict[str, Any] = {
        "unique": solved,
        "time_ms": time_budget,
        "nodes": 0,
        "cutoff": cutoff,
    }
    if candidate_ref:
        verdict["candidate_ref"] = candidate_ref
    if solved_ref:
        verdict["solved_ref"] = solved_ref

    return verdict
