# sudoku_generator.py
# Generate full solutions, reduce to puzzles with uniqueness and logical solvability,
# and score "interest" using sudoku_solver.LogicSolver steps.

from typing import List, Tuple, Optional, Dict
import random, time, json
import importlib.util, sys

# Import solver module from sibling path (adjust if needed)
from pathlib import Path
here = Path(__file__).resolve().parent
sol_path = here / "sudoku_solver.py"
spec = importlib.util.spec_from_file_location("sudoku_solver", str(sol_path))
sudoku_solver = importlib.util.module_from_spec(spec)
sys.modules["sudoku_solver"] = sudoku_solver
spec.loader.exec_module(sudoku_solver)

Grid = sudoku_solver.Grid
LogicSolver = sudoku_solver.LogicSolver

# ---------- Utils ----------

def grid_copy(g: List[List[int]]) -> List[List[int]]:
    return [row[:] for row in g]

def to_string(g: List[List[int]]) -> str:
    return ''.join(str(g[r][c] or 0) for r in range(9) for c in range(9))

def from_string(s: str) -> List[List[int]]:
    s = s.strip().replace("\n", "").replace(" ", "")
    assert len(s) == 81
    grid = []
    k = 0
    for r in range(9):
        row = []
        for c in range(9):
            ch = s[k]; k += 1
            row.append(int(ch) if ch.isdigit() and ch != '0' else 0)
        grid.append(row)
    return grid

def print_grid(g: List[List[int]]) -> str:
    lines = []
    for r in range(9):
        if r % 3 == 0:
            lines.append("+-------+-------+-------+")
        row = []
        for c in range(9):
            v = g[r][c]
            row.append(str(v) if v != 0 else ".")
            if c % 3 == 2:
                row.append("|")
        lines.append("| " + " ".join(row[:-1]) + " ")
    lines.append("+-------+-------+-------+")
    return "\n".join(lines)

# ---------- Full solution generator ----------


def generate_full_solution(seed=None, time_limit=1.5):
    rng = random.Random(seed)
    start = time.monotonic()

    # bitmask-представление кандидатов (1..9 -> биты 0..8)
    FULL = (1 << 9) - 1  # 0b111111111

    # Сетка и маски ограничений
    grid = [[0]*9 for _ in range(9)]
    row_mask = [0]*9    # какие цифры уже стоят в строке (битовая маска)
    col_mask = [0]*9
    box_mask = [0]*9

    def bidx(r, c): return (r//3)*3 + c//3

    # Кандидаты для ячейки как битмаска: разрешено то, чего нет в строке/столбце/боксе
    def cand_mask(r, c):
        used = row_mask[r] | col_mask[c] | box_mask[bidx(r, c)]
        return FULL & ~used

    # Быстрое преобразование битмаски -> список цифр
    def bits_to_list(bits):
        out = []
        v = 1
        d = 1
        while v <= FULL:
            if bits & v: out.append(d)
            v <<= 1; d += 1
        return out

    # MRV: найти незаполненную клетку с минимальным числом кандидатов
    def select_cell():
        best = None
        best_count = 10
        # небольшой рандом в обходе клеток, чтобы сетки были разнообразны
        rows = list(range(9)); cols = list(range(9))
        rng.shuffle(rows); rng.shuffle(cols)
        for r in rows:
            for c in cols:
                if grid[r][c] == 0:
                    m = cand_mask(r, c)
                    k = m.bit_count()
                    if k == 0:
                        return (r, c, 0)  # dead end
                    if k < best_count:
                        best = (r, c, m)
                        best_count = k
                        if k == 1:
                            return best  # ранний выход
        return best  # может быть None, если всё заполнено

    def place(r, c, d):
        bit = 1 << (d-1)
        grid[r][c] = d
        row_mask[r] |= bit
        col_mask[c] |= bit
        box_mask[bidx(r, c)] |= bit

    def unplace(r, c, d):
        bit = 1 << (d-1)
        grid[r][c] = 0
        row_mask[r] &= ~bit
        col_mask[c] &= ~bit
        box_mask[bidx(r, c)] &= ~bit

    # Рекурсивный поиск с тайм-аутом
    def solve():
        # тайм-аут, чтобы не зависать
        if time.monotonic() - start > time_limit:
            return False
        cell = select_cell()
        if cell is None:
            return True  # всё заполнено
        r, c, m = cell
        if m == 0:
            return False
        # случайный порядок кандидатов для разнообразия
        cand = bits_to_list(m)
        rng.shuffle(cand)
        for d in cand:
            place(r, c, d)
            if solve():
                return True
            unplace(r, c, d)
        return False

    if solve():
        return grid

    # --- Фолбэк: латинская заготовка + перемешивания бэндов/стаков ---
    base = [[((r*3 + r//3 + c) % 9) + 1 for c in range(9)] for r in range(9)]

    def shuffle_rows_in_bands(G):
        for br in (0,3,6):
            order = [br, br+1, br+2]
            rng.shuffle(order)
            rows = [G[i] for i in order]
            G[br:br+3] = rows

    def shuffle_cols_in_stacks(G):
        T = list(map(list, zip(*G)))
        for bc in (0,3,6):
            order = [bc, bc+1, bc+2]
            rng.shuffle(order)
            cols = [T[i] for i in order]
            T[bc:bc+3] = cols
        return [list(r) for r in zip(*T)]

    def shuffle_bands(G):
        order = [0,3,6]
        rng.shuffle(order)
        return [row for b in order for row in G[b:b+3]]

    def shuffle_stacks(G):
        T = list(map(list, zip(*G)))
        order = [0,3,6]
        rng.shuffle(order)
        T2 = [col for s in order for col in T[s:s+3]]
        return [list(r) for r in zip(*T2)]

    def permute_digits(G):
        p = list(range(1,10))
        rng.shuffle(p)
        mp = {i+1:p[i] for i in range(9)}
        for r in range(9):
            for c in range(9):
                G[r][c] = mp[G[r][c]]

    G = [row[:] for row in base]
    G = shuffle_bands(G)
    G = shuffle_stacks(G)
    shuffle_rows_in_bands(G)
    G = shuffle_cols_in_stacks(G)
    permute_digits(G)
    return G
# ---------- Uniqueness checker (count up to 2) ----------

def has_unique_solution(puzzle: List[List[int]], limit: int = 2) -> bool:
    rows_used = [set() for _ in range(9)]
    cols_used = [set() for _ in range(9)]
    boxes_used = [set() for _ in range(9)]
    g = grid_copy(puzzle)

    def box_idx(r, c): return (r//3)*3 + (c//3)

    empties = []
    for r in range(9):
        for c in range(9):
            v = g[r][c]
            if v == 0:
                empties.append((r, c))
            else:
                bi = box_idx(r, c)
                rows_used[r].add(v); cols_used[c].add(v); boxes_used[bi].add(v)

    def candidates(r, c):
        bi = box_idx(r, c)
        return {d for d in range(1, 10) if d not in rows_used[r] and d not in cols_used[c] and d not in boxes_used[bi]}

    empties.sort(key=lambda rc: len(candidates(*rc)))
    solutions = 0

    def backtrack(i: int) -> bool:
        nonlocal solutions
        if solutions >= limit:
            return True
        if i == len(empties):
            solutions += 1
            return False
        r, c = empties[i]
        bi = box_idx(r, c)
        cand = list(candidates(r, c))
        if not cand:
            return False
        for d in cand:
            g[r][c] = d
            rows_used[r].add(d); cols_used[c].add(d); boxes_used[bi].add(d)
            stop = backtrack(i + 1)
            rows_used[r].remove(d); cols_used[c].remove(d); boxes_used[bi].remove(d)
            g[r][c] = 0
            if stop and solutions >= limit:
                return True
        return False

    backtrack(0)
    return solutions == 1

# ---------- Interest scorer (updated) ----------

TECH_WEIGHTS = {
    "Naked Single": 0.7,
    "Hidden Single": 1.0,
    "Locked Candidates (Pointing)": 1.6,
    "Locked Candidates (Claiming)": 1.7,
    "Naked Pairs": 1.9,
    "Hidden Pairs": 2.1,
    "X-Wing (Rows)": 3.2,
    "X-Wing (Cols)": 3.2,
    "XY-Wing": 3.6,
    "Swordfish (Rows)": 4.0,
    "Swordfish (Cols)": 4.0,
}

ADVANCED = {
    "Naked Pairs", "Hidden Pairs",
    "Locked Candidates (Pointing)", "Locked Candidates (Claiming)",
    "X-Wing (Rows)", "X-Wing (Cols)", "XY-Wing",
    "Swordfish (Rows)", "Swordfish (Cols)",
}

def score_interest(steps):
    if not steps:
        return 0.0, {"reason": "no steps"}

    techs = [s.technique for s in steps]
    uniq = sorted(set(techs))

    # 1) Разнообразие техник (скромно)
    diversity = min(42.0, len(uniq) * 6.0)

    # 2) Насыщенность приёмами (весами)
    wsum = sum(TECH_WEIGHTS.get(t, 1.0) for t in techs)
    richness = min(36.0, wsum * 0.55)

    # 3) Кривая: больше продвинутых именно в середине (фаза B)
    phaseA = [t for t in steps if (t.phase or "B") == "A"]
    phaseB = [t for t in steps if (t.phase or "B") == "B"]
    phaseC = [t for t in steps if (t.phase or "B") == "C"]
    def adv_share(lst): 
        return (sum(1 for s in lst if s.technique in ADVANCED) / max(1, len(lst)))
    advA, advB, advC = adv_share(phaseA), adv_share(phaseB), adv_share(phaseC)
    curve_bonus = max(0.0, (advB - max(advA, advC))) * 12.0

    # 4) Бонус за присутствие «тяжёлых» приёмов
    has_xwing = any(t in {"X-Wing (Rows)", "X-Wing (Cols)"} for t in techs)
    has_xywing = "XY-Wing" in techs
    has_sword = any(t.startswith("Swordfish") for t in techs)
    advanced_presence = (4.0 if has_xwing else 0.0) + (6.0 if has_xywing else 0.0) + (8.0 if has_sword else 0.0)

    # 5) Штрафы за монотонность
    longest_run, cur = 1, 1
    for i in range(1, len(techs)):
        if techs[i] == techs[i-1]:
            cur += 1
            longest_run = max(longest_run, cur)
        else:
            cur = 1
    monotony_penalty = max(0.0, (longest_run - 5) * 1.8)

    singles_cnt = sum(1 for t in techs if t in {"Naked Single", "Hidden Single"})
    singles_share = singles_cnt / len(techs)
    singles_penalty = max(0.0, (singles_share - 0.65) * 30.0)  # до ~10–12 очков

    # Итог
    score = diversity + richness + curve_bonus + advanced_presence - monotony_penalty - singles_penalty

    # Если совсем одни синглы — мягкий «потолок», но не 20, как раньше
    if set(uniq) <= {"Naked Single", "Hidden Single"}:
        score = min(score, 28.0)

    report = {
        "diversity": diversity,
        "richness": richness,
        "curve": {"advA": advA, "advB": advB, "advC": advC, "bonus": curve_bonus},
        "advanced_presence": advanced_presence,
        "monotony_penalty": monotony_penalty,
        "singles_penalty": singles_penalty,
        "unique_techniques": uniq,
        "steps": len(techs),
        "score": score,
    }
    return score, report

# ---------- Reducer ----------

def symmetric_pairs() -> List[Tuple[Tuple[int,int], Tuple[int,int]]]:
    pairs = []
    for r in range(9):
        for c in range(9):
            r2, c2 = 8 - r, 8 - c
            if (r, c) <= (r2, c2):
                pairs.append(((r, c), (r2, c2)))
    return pairs

def reduce_with_checks(solution: List[List[int]], target_score: float, rng: random.Random, time_budget: float = 10.0):
    puzzle = grid_copy(solution)
    pairs = symmetric_pairs()
    rng.shuffle(pairs)

    best_snapshot = (grid_copy(puzzle), [], 0.0, {"reason": "init"})
    t0 = time.time()

    for ((r1, c1), (r2, c2)) in pairs:
        if time.time() - t0 > time_budget:
            break
        if puzzle[r1][c1] == 0 and puzzle[r2][c2] == 0:
            continue

        saved1, saved2 = puzzle[r1][c1], puzzle[r2][c2]
        puzzle[r1][c1] = 0
        puzzle[r2][c2] = 0

        if not has_unique_solution(puzzle):
            puzzle[r1][c1], puzzle[r2][c2] = saved1, saved2
            continue

        g = Grid(grid_copy(puzzle))
        solver = LogicSolver(g)
        status, steps = solver.solve_with_log()
        if status != "solved":
            puzzle[r1][c1], puzzle[r2][c2] = saved1, saved2
            continue

        score, report = score_interest(steps)

        if score >= best_snapshot[2] or best_snapshot[2] < target_score:
            best_snapshot = (grid_copy(puzzle), steps, score, report)

        clues = sum(1 for r in range(9) for c in range(9) if puzzle[r][c] != 0)
        if clues <= 28 and score < 10.0:
            # только на поздней стадии считаем низкий скор признаком скуки
            puzzle[r1][c1], puzzle[r2][c2] = saved1, saved2

    final_puzzle, steps, score, report = best_snapshot
    return final_puzzle, steps, score, report

# ---------- Minimality sweep ----------

def enforce_minimality(puzzle, rng, symmetry: str = "central", time_budget: float = 6.0):
    """
    Удаляем лишние данные до состояния минимальности.
    symmetry: "central" — удаляем парами по центральной симметрии; "none" — по одной.
    """
    p = grid_copy(puzzle)
    start = time.time()
    changed = True

    if symmetry == "central":
        # Парное удаление по центральной симметрии
        while changed and (time.time() - start) < time_budget:
            changed = False
            pairs = symmetric_pairs()
            rng.shuffle(pairs)
            for ((r1, c1), (r2, c2)) in pairs:
                if (time.time() - start) >= time_budget:
                    break
                if p[r1][c1] == 0 and p[r2][c2] == 0:
                    continue
                saved1, saved2 = p[r1][c1], p[r2][c2]
                p[r1][c1] = 0; p[r2][c2] = 0
                if has_unique_solution(p):
                    g = Grid(grid_copy(p)); status, _ = LogicSolver(g).solve_with_log()
                    if status == "solved":
                        changed = True
                        continue
                # откат
                p[r1][c1], p[r2][c2] = saved1, saved2
    else:
        # По одной клетке (может разрушить симметрию, зато часто даёт более «чистую» минимальность)
        while changed and (time.time() - start) < time_budget:
            changed = False
            coords = [(r, c) for r in range(9) for c in range(9) if p[r][c] != 0]
            rng.shuffle(coords)
            for (r, c) in coords:
                if (time.time() - start) >= time_budget:
                    break
                saved = p[r][c]
                p[r][c] = 0
                if has_unique_solution(p):
                    g = Grid(grid_copy(p)); status, _ = LogicSolver(g).solve_with_log()
                    if status == "solved":
                        changed = True
                        continue
                p[r][c] = saved
    return p

# ---------- Top-level generation (MODIFIED) ----------

def generate_interesting(seed: Optional[int] = None, target_score: float = 40.0, time_budget: float = 20.0):
    """
    Generates a puzzle by attempting to find one that meets the target_score within the total time_budget.
    Each attempt gets a fixed internal time budget to ensure quality.
    """
    rng = random.Random(seed)
    t0 = time.time()
    best = None
    
    # Internal budget for a single generation attempt (reduce + minimize).
    # This ensures each attempt is thorough, regardless of the total time_budget.
    single_attempt_budget = 15.0 
    
    # Allocate time for the main stages of a single attempt.
    reduce_time = single_attempt_budget * 0.7  # 70% of time for the most critical step
    minimize_time = single_attempt_budget * 0.3 # 30% for final cleanup

    # Main loop: keep trying until total time is up or target score is met.
    while time.time() - t0 < time_budget:
        
        # --- Stage 1: Create a new full solution ---
        solution = generate_full_solution(seed=rng.randrange(1<<30))
        
        # --- Stage 2: Reduce the solution to a puzzle, searching for interestingness ---
        puzzle, _, _, _ = reduce_with_checks(
            solution, target_score, rng, time_budget=reduce_time
        )
        
        # --- Stage 3: Make the puzzle minimal ---
        puzzle = enforce_minimality(
            puzzle, rng, symmetry="central", time_budget=minimize_time
        )

        # --- Stage 4: Re-analyze the final puzzle to get its definitive score ---
        g = Grid(grid_copy(puzzle))
        status, steps = LogicSolver(g).solve_with_log()
        
        score = 0.0
        report = {}
        if status == "solved":
            score, report = score_interest(steps)
        
        # --- Stage 5: Check if this puzzle is the best one found so far ---
        if best is None or score > best[2]:
            best = (puzzle, solution, score, report, steps)
            # Optional: print progress
            # print(f"  New best puzzle found! Score: {score:.1f}")

        # --- Stage 6: Check exit conditions ---
        if score >= target_score:
            # Found a puzzle that meets the criteria, exit early.
            break
        
        if time.time() - t0 > time_budget - single_attempt_budget:
            # Not enough time left for another full, high-quality attempt.
            break

    return best

# ---------- CLI demo ----------

if __name__ == "__main__":
    seed = 12345
    # Use a larger time budget to see the effect of the new logic
    result = generate_interesting(seed=seed, target_score=35.0, time_budget=30.0)
    if result is None:
        print("Failed to generate within time budget.")
    else:
        puzzle, solution, score, report, steps = result
        print("Puzzle:")
        print(print_grid(puzzle))
        print("\nSolution:")
        print(print_grid(solution))
        print(f"\nInterest score: {score:.1f}")
        print("Unique techniques:", report.get("unique_techniques"))
        bundle = {
            "puzzle": to_string(puzzle),
            "solution": to_string(solution),
            "score": score,
            "report": report,
            "steps": [s.to_dict() for s in steps],
        }
        with open("interesting_sudoku.json", "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)
        print("Saved JSON to interesting_sudoku.json")