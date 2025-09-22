# Parameter descriptions for `config.toml`

## [PUZZLE]
- `name`: Identifier used for the generated puzzle pack.
- `size`: Width and height of the square Sudoku grid in cells.
- `alphabet`: Symbols that can appear in the grid; ordered as they should be rendered.

### [PUZZLE.block]
- `rows`: Number of grid rows grouped together to form a block.
- `cols`: Number of grid columns grouped together to form a block.

## [LIMITS]
- `solver_timeout_ms`: Maximum time allowed for the solver to search for a solution, in milliseconds.

## [RENDER]
- `format`: Output format for the rendered puzzles (for example, PDF).
- `template`: Rendering template or theme to apply when drawing the puzzles.
- `page`: Target paper size keyword used by the renderer.
- `dpi`: Resolution of the rendered output, in dots per inch.

## [pdf]
- `total_puzzles`: Number of Sudoku puzzles to include in the pack.
- `pages`: Number of pages the pack should span.
- `default_target_score`: Baseline difficulty score targeted during generation.
- `default_time_budget`: Default time budget in minutes assumed for solving each puzzle.

### [pdf.layout]
- `rows`: Number of puzzle rows per page layout.
- `cols`: Number of puzzle columns per page layout.

### [pdf.page]
- `width_cm`: Page width in centimetres.
- `height_cm`: Page height in centimetres.
- `margin_cm`: Uniform page margin in centimetres.
- `gap_cm`: Horizontal and vertical gap between puzzle grids in centimetres.
- `footer_offset_cm`: Distance from the bottom margin to any footer elements in centimetres.

### [pdf.rendering]
- `font_scale_factor`: Scaling applied to the base font sizes when rendering numbers and annotations.

### [pdf.output]
- `filename_prefix`: Prefix used when naming exported PDF files.

### [pdf.fallback]
- `seed_multiplier`: Multiplier applied to the random seed when retrying puzzle generation.
- `reduce_time_share`: Portion of the available fallback time dedicated to clue reduction.
- `min_time_budget`: Minimum allowed solving time budget for fallback puzzles, in minutes.

## [generator.full_solution]
- `time_limit`: Maximum time, in seconds, permitted for building an initial full solution grid.

## [generator.reduce]
- `time_budget`: Time, in seconds, allocated to the clue reduction process.
- `min_clues`: Minimum number of given clues to keep in the puzzle.
- `low_score_threshold`: Difficulty score threshold below which puzzles are considered too easy and can be discarded.

## [generator.minimality]
- `time_budget`: Time, in seconds, allocated to verifying minimality.
- `symmetry`: Symmetry strategy enforced while testing puzzle minimality.

## [generator.interesting]
- `target_score`: Desired difficulty score for selecting interesting puzzles.
- `time_budget`: Time, in seconds, allotted to the interestingness search stage.
- `single_attempt_budget`: Maximum time allowed for a single interestingness attempt.
- `reduce_share`: Fraction of time spent on reduction during this stage.
- `minimize_share`: Fraction of time spent on minimality checks during this stage.

## [interest_scoring]
- `diversity_cap`: Upper limit for diversity contribution to the interest score.
- `diversity_step`: Step size used when measuring diversity gains between puzzles.
- `richness_cap`: Maximum richness contribution allowed in scoring.
- `richness_factor`: Factor applied to scale richness-based bonuses.
- `curve_bonus_scale`: Controls how strongly solving curve bonuses affect the score.
- `xwing_bonus`: Extra points granted when an X-Wing technique is required.
- `xywing_bonus`: Extra points granted when an XY-Wing technique is required.
- `swordfish_bonus`: Extra points granted when a Swordfish technique is required.
- `monotony_free_run`: Number of consecutive puzzles allowed without variety before penalties apply.
- `monotony_penalty`: Penalty applied when the monotony limit is exceeded.
- `singles_share_limit`: Maximum proportion of single-step techniques before penalties trigger.
- `singles_penalty_scale`: Scaling factor applied to penalties for excessive single techniques.
- `singles_score_cap`: Upper bound on the score contribution from single-step techniques.

### [interest_scoring.advanced]
- `techniques`: Ordered list of advanced solving techniques that the generator monitors and rewards.

### [interest_scoring.weights]
- `<technique name>`: Relative weight assigned to each solving technique when computing puzzle difficulty.
