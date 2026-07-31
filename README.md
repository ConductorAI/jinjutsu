# Jinjutsu

Read a Jinja template and answer two questions in one pass:

1. **What data does this template need?** Not just the variable names, but their shape — is `sections`
   a list of objects with a `title` field, or a list of strings? Jinja's own
   `meta.find_undeclared_variables` gives you names only.
2. **What is wrong with it?** In plain language a non-programmer can act on, with a line number, the
   text that caused it, and the edit that fixes it.

Built for templates authored in Word and rendered with [docxtpl], so it understands docxtpl's tag
syntax and the mistakes Word introduces on its own — curly quotes, stray spaces inside tags, and tags
split across paragraphs.

```
Line 2: Field 'items' collides with a built-in method
  Found: {{ store.items }}
  Fix:   {{ store['items'] }}
  Reason: Jinja reads '.items' as the value's own method, so the document renders the method
          instead of your value. Use bracket syntax.
  {{ store.items }}
```

## Why not just use Jinja's parser

Jinja's messages are written for programmers, and they blame the wrong line. `Encountered unknown tag
'endif'` on line 40 is a useless thing to show someone whose real mistake was typing `{ % if x %}` on
line 1.

Measured against three hand-built suites: 21 valid templates that must not be flagged, 29 with real
breakage, and 10 that parse cleanly but render wrong.

|                  | valid templates falsely flagged | real breakage caught | semantic gotchas caught |
| ---------------- | ------------------------------: | -------------------: | ----------------------: |
| **This package** |                        **0/21** |            **28/29** |                **8/10** |
| Plain Jinja      |                            4/21 |                24/29 |                    0/10 |
| [jinjaninja]     |                            4/21 |                 4/29 |                    0/10 |

Nothing else catches the semantic class at all: a template that parses perfectly and still renders
`{'field': ...}` into a finished document.

In fairness to [jinjaninja], it bills itself as a style enforcement tool, so correctness cases are
not what it set out to catch — it is in the table because it is the closest thing to a Jinja linter
on PyPI, and it is the only one of the three that checks style at all.

<details open>
<summary><b>Full case-by-case comparison</b> (36 cases)</summary>

**Legend** — ✅ detected, with a message naming the mistake · ⚠️ detected, but only a raw parser
message · ❌ no finding, template reported clean

| Error                                                              | This package                                | Plain Jinja                             | jinjaninja           |
| ------------------------------------------------------------------ | ------------------------------------------- | --------------------------------------- | -------------------- |
| **Broken delimiters**                                              |                                             |                                         |                      |
| `{{ x }` — missing brace                                           | ✅ named + fix                              | ⚠️ unexpected `'}'`                      | ❌                   |
| `{% x }` — missing `%`                                             | ✅ named + fix                              | ⚠️ unknown tag `'x'`                     | ❌                   |
| `{ % if x %}` — space after `{`                                    | ✅                                          | ⚠️ unknown tag `'endif'` — wrong tag     | ✅                   |
| `{% if x % }` — space before `}`                                   | ✅                                          | ⚠️ unexpected `'}'`                      | ✅                   |
| `{if% x %}` — transposed `%`                                       | ✅                                          | ⚠️ unknown tag `'endif'` — wrong tag     | ❌                   |
| `{ if x %}` — missing opening `%`                                  | ✅                                          | ⚠️ unknown tag `'endif'` — wrong tag     | ❌                   |
| `{ { x }}` — split brace                                           | ✅ named + fix + reason                     | ❌                                      | ✅                   |
| `{{ {{ x }}` — doubled opening                                     | ⚠️ generic                                   | ⚠️ expected token `':'`                  | ✅                   |
| `{{{ x }}}` — triple brace                                         | ⚠️ generic                                   | ⚠️ expected token `':'`                  | ❌                   |
| **Structure**                                                      |                                             |                                         |                      |
| Unclosed `{% for %}` / `{% if %}`                                  | ✅ names the tag and the count              | ⚠️ unexpected end of template            | ❌                   |
| Orphan `{% endif %}`                                               | ✅                                          | ⚠️ unknown tag `'endif'`                 | ❌                   |
| Crossed nesting                                                    | ⚠️ generic                                   | ⚠️ unknown tag `'endfor'`                | ❌                   |
| Unknown tag (`{% forach %}`)                                       | ✅                                          | ⚠️ unknown tag `'forach'`                | ❌                   |
| Unclosed `{% set %}` block                                         | ✅ names the missing end tag                | ⚠️ unexpected end of template            | ❌                   |
| **Expressions**                                                    |                                             |                                         |                      |
| `{{ a. }}` — trailing dot                                          | ✅ "invalid variable name"                  | ⚠️ expected name or number               | ❌                   |
| `{% if x = 1 %}` — `=` for `==`                                    | ✅ guidance                                 | ⚠️ expected 'end of statement block'     | ❌                   |
| Smart quotes `“ ”` from Word                                       | ⚠️ generic                                   | ⚠️ unexpected char `'“'` at 11           | ❌                   |
| `{{ fiscal-year }}`                                                | ✅ explains subtraction, offers spaced form | ❌                                      | ❌                   |
| `{% if fiscal-year %}`                                             | ✅ same check                               | ❌                                      | ❌                   |
| `{% for r in funding-rows %}`                                      | ✅ same check                               | ❌                                      | ❌                   |
| **Semantic** — passes Jinja's parser, wrong at render              |                                             |                                         |                      |
| `.items` / `.keys` / `.values` — dict methods                      | ✅ + bracket fix                            | ❌                                      | ❌                   |
| `.count` / `.index` / `.sort` — list methods                       | ✅ + bracket fix, all 19 names              | ❌                                      | ❌                   |
| Whole object printed with `{{ }}`                                  | ✅                                          | ❌                                      | ❌                   |
| Whole list printed with `{{ }}`                                    | ✅                                          | ❌                                      | ❌                   |
| Same name used as both scalar and object                           | ✅                                          | ❌                                      | ❌                   |
| Unknown filter (`{{ x \| to_json }}`)                              | ❌ zero variables, no warning               | ❌                                      | ❌                   |
| **docxtpl-specific**                                               |                                             |                                         |                      |
| `{%tr %}` / `{%p %}` / `{{r }}` prefixed tags                      | ✅ correctly ignored                        | ❌ false positive — unknown tag `'tr'`  | ❌ false positive    |
| `{% vm %}` `{% hm %}` `{% colspan n %}` `{% cellbg c %}`, used well | ✅ ignored, arguments extracted             | ❌ false positive — unknown tag `'tr'`  | ❌ false positive    |
| `{% cellbg %}` with no argument                                    | ⚠️ generic                                   | ⚠️ unknown tag `'cellbg'`                | ❌                   |
| `{% vm %}` / `{% hm %}` outside a loop                             | ✅ names the tag and the fix                | ⚠️ unknown tag `'vm'`                    | ❌                   |
| **Robustness** (docx authoring artifacts)                          |                                             |                                         |                      |
| Tag split across paragraphs — variable extraction                  | ✅ unaffected, shape still inferred         | ✅ parses                               | ❌                   |
| Tag split across paragraphs — break at a token boundary            | ✅ folds the break, reports normally        | ❌                                      | ❌                   |
| Tag split across paragraphs — break inside an identifier           | ⚠️ missed if the break splits the name       | ❌                                      | ❌                   |
| Commented-out code in `{# … #}`                                    | ✅ correctly ignored                        | ✅ ignored                              | ❌                   |
| Commented-out `{% if %}`                                           | ✅ correctly ignored                        | ✅ ignored                              | ❌                   |
| **Style**                                                          |                                             |                                         |                      |
| Tag spacing, casing, tabs, indentation                             | ❌ by design — false positives on docx      | ❌                                      | ✅                   |

</details>

## Usage

```python
from jinjutsu import analyze_jinja_template

report = analyze_jinja_template(template_text)

report.variables    # dict[str, VariableNode] — each name and its inferred shape
report.diagnostics  # list[str] — formatted strings, ready to show the user
```

`analyze_jinja_template` parses once and shares that result between the two passes: the AST walk in
`variable_tree.py` and the text checks in `checks/`. It never raises for a malformed template — a
parse failure comes back as a diagnostic.

## The variable tree

`report.variables` maps each top-level name to a `VariableNode`. Given:

```jinja
{{ case.header.title }}
{% for s in case.sections %}{{ s.name }}{% endfor %}
{% if case.sealed %}SEALED{% endif %}
```

```
case                object           -> {"header": ..., "sections": [...], "sealed": true}
|-- header          object           -> {"title": "..."}
|   `-- title       string
|-- sections        list of objects  -> [{"name": "..."}, {"name": "..."}]
|   `-- name        string              a field on each section, not on the list
`-- sealed          boolean
```

A `VariableNode` is a tagged union, discriminated on `kind`:

| node          | `kind`      | children                                    |
| ------------- | ----------- | ------------------------------------------- |
| `ObjectNode`  | `object`    | `properties: dict[str, VariableNode]`       |
| `ListNode`    | `list`      | `items: VariableNode` — one element         |
| `StringNode`  | `string`    | leaf                                        |
| `BooleanNode` | `boolean`   | leaf                                        |
| `NumberNode`  | `number`    | leaf — declared, nothing infers it yet      |
| `UnknownNode` | `unknown`   | leaf — the name is required, its shape is not evidenced |

Objects and lists are the interior nodes. Two things are worth knowing:

- **A list describes its element through `items`, not through its own fields.** `sections.items` is
  the shape of one section, so `sections.items.properties.name` says every section has a name, never
  that the list itself has one. A loop is what puts it there: `{% for s in sections %}` binds `s` to
  the element slot of `sections`, so `{{ s.name }}` writes `name` into that element.
- **`unknown` is not a failure.** It means Jinja requires the name but nothing in the template says
  what shape it takes — `{% for x in xs %}` with `x` never used leaves `xs.items` unknown. Guessing
  `string` there, which an earlier version did, reads as evidence that was never gathered.

### How types are decided

| template                                    | inferred                                        |
| ------------------------------------------- | ----------------------------------------------- |
| `{{ x }}`                                   | `string`                                        |
| `{% if x %}`                                | `boolean` — a guard, never rendered             |
| `{% if x %}{{ x }}{% endif %}`              | `string` — rendering pins it                    |
| `{% if x == true %}`                        | `boolean`                                       |
| `{% if x == 'FINAL' %}`, `{% if x == 1 %}`  | `string`                                        |
| `{% if x %}{{ x.title }}{% endif %}`        | `object` — the guard was an existence check     |
| `{% for s in xs %}{{ s }}{% endfor %}`      | `xs`: list of strings                           |
| `{% for s in xs %}{{ s.a }}{% endfor %}`    | `xs`: list of objects                           |
| `{{ xs[0].a }}`, `{{ xs.0.a }}`             | `xs`: list of objects                           |
| `{{ m[0][1] }}`                             | `m`: list of lists of strings                   |
| `{% for f in fs %}{% if f %}{% endif %}{% endfor %}` | `fs`: list of booleans                 |
| `{% for x in xs %}body{% endfor %}`         | `xs`: list, element `unknown` — nothing reads it |
| `{{ r['items'] }}`                          | `r`: object with an `items` field, not an index  |

Names the template invents are never reported, since nobody supplies them: loop targets,
`{% set %}` targets, and macro, call and with block parameters.

## Diagnostics

`report.diagnostics` is a list of formatted strings you can show the user directly. There are three
layouts, each built by one helper.

`warning_to_string` in `utils/string_utils.py` — most warnings, wherever there is a line to point at:

```
Line 4: 'a' is used as both a value and an object
  Found: a.b
  Fix:   give the two uses different names        <- three spaces, aligned
  Reason: ...                                    <- optional
  {{ a.b }}                                      <- optional source line
```

`_tag_count` in `checks/blocks.py` — a count that is wrong across the whole template, so there is no
one line to blame:

```
Mismatched loop tags
  Found: 1 {% for %} tag(s) but 0 {% endfor %} tag(s)
  Fix: Each {% for %} must have a corresponding {% endfor %}   <- one space
```

`_syntax_error` in `checks/parser.py` — Jinja's own message, wrapped in friendlier guidance and kept
underneath:

```
Line 2: Unexpected 'b' after the expression
  {% if a b c %}
  Error: expected token 'end of statement block', got 'b'
```

### Which warnings survive

The custom checks run first, and Jinja's parser is the fallback for anything they miss. Suppression
follows one rule: **a check silences Jinja's error only when both are looking at the same mistake.**

- A **broken delimiter** silences it entirely. Jinja reads the tag as plain text, so every error
  after that is a consequence — it will blame an innocent end tag pages below. The tag counts are
  suppressed for the same reason: they cannot see an opener they do not recognize, so they would
  claim zero `{% if %}` tags when one is sitting right there, just broken.
- A **tag-count mismatch** silences only Jinja's block-balance errors (`unexpected end of template`,
  `unknown tag 'end…'`), which restate the same imbalance less clearly. Any other Jinja error is an
  independent problem and is reported alongside.
- Everything else — hyphens, built-in method collisions, cell merges — never silences anything, since
  none of them affects whether the template parses.

This matters. A mismatched tag used to hide a genuine expression error further down, so authors fixed
one problem and only then discovered the next.

## docxtpl support

docxtpl tags are rewritten to vanilla Jinja before parsing: the `tr`/`tc`/`p`/`r` row, cell,
paragraph and run prefixes are blanked, `{% vm %}` and `{% hm %}` cell merges are blanked, and
`{% colspan n %}` / `{% cellbg c %}` become `{{ n }}` / `{{ c }}`, which is what docxtpl substitutes.

**Every rewrite preserves character count and newline positions.** Whitespace inside a tag is
insignificant to Jinja, which is what leaves room to pad. Widening or narrowing the text would
silently shift every diagnostic after a docxtpl tag, and dropping a newline would shift every
diagnostic in the rest of the template.

## Performance

Wall-clock for one full `analyze_jinja_template` call against synthetic documents of the shape given,
best of 3 runs. Both columns were measured in the same process on the same machine, so the ratios are
meaningful even though the absolute numbers are not portable.

| shape (chars, lines)                                            | this package |  jinjaninja |
| --------------------------------------------------------------- | -----------: | ----------: |
| 100 pg prose, 6 tags (301 KB, 750 lines)                        |        23 ms |        5 ms |
| 500 pg prose, 6 tags (1.5 MB, 3750 lines)                       |       111 ms |       26 ms |
| 500 pg, 6 tags, prose with `100%` and `{see Exhibit C, § 4(b)}` |       115 ms |       28 ms |
| 1000 pg prose, 6 tags (3.0 MB)                                  |       220 ms |       52 ms |
| 500 pg prose, 600 tags                                          |       716 ms |     1343 ms |
| 500 pg, 6 tags, one long line — tags at the end                 |        97 ms |       21 ms |
| 500 pg, 6 tags, one long line — tags spread through it          |       114 ms | **19349 ms** |

On ordinary prose a line-oriented linter is 4× quicker, and at these magnitudes neither number
matters. Two rows are worth reading closely:

- **Cost tracks the number of tags, not document length.** 600 tags in 1.5 MB costs more than 6 tags
  in 3.0 MB. That suits documents that are mostly prose, and it is where the ordering flips.
- **A docx that extracts to one unbroken line is a normal input here and a trap for a line-oriented
  linter.** jinjaninja goes from 21 ms to 19 seconds on the same bytes depending on *where the tags
  sit* in that line, because its style regexes use a greedy `(.+\w+)?` that backtracks across
  everything following a tag. This package matches tags across newlines instead of per line, so all
  three one-long-line variants land within 20 ms of each other.

<details open>
<summary><b>Where the superlinear costs are</b></summary>

**An axis is one thing you can make bigger about a template.** Every cost below is a product of two
of them, so each row names its own pair — `find_tags`, for example, costs tags × bytes, and a template
with many tags *and* many bytes is what makes it expensive.

The `O(...)` column is by code inspection. The slope columns are measured: time one site in isolation
across a geometric size range, then take the local slope of log(time) against log(size) between
adjacent points. Local slopes, not one global fit — several sites are still dominated by fixed
overhead at small n, and fitting across that region is what makes a genuinely quadratic site look
like `n^1.5`.

Two sweeps per site. **One axis** holds the other fixed and grows one. **Both** grows them together in
the fixed ratio given, so cost `A × B` should come out near `n²` — that column confirms the product,
it does not discover anything.

| # | site                                           | cost by inspection                              | axes (A, B)                              | one axis at a time              | both, in ratio               |
| - | ---------------------------------------------- | ----------------------------------------------- | ---------------------------------------- | ------------------------------- | ---------------------------- |
| 1 | `find_tags` line numbering                     | O(M × N)                                        | M tags, N bytes                          | n^1.01 tags, n^0.96 bytes       | n^1.96  (N = 200 M)          |
| 2 | `warning_to_string(source_line=)`              | O(W × L)                                        | W warnings, L embedded line length       | n^1.03 warnings, n^0.17 length  | n^1.14 → 1.58, still climbing (1:1) |
| 3 | `VariableTreeVisitor._guarded`                 | O(G × U)                                        | G guards `{% if x %}`, U uses `{{ a.b }}`| n^0.82 guards, n^0.81 uses      | n^1.71 → 1.90, approaching 2 (1:1) |
| 4 | `replace_comments_with_spaces`                 | O(C × N)                                        | C unclosed `{#`, N bytes                 | n^1.01 opens, n^1.02 bytes      | n^2.02  (N = 500 C)          |
| 5 | `check_malformed_tags` regexes                 | O(D × L)                                        | D unclosed delimiters, L line length     | n^0.96 opens, n^0.98 length     | n^1.94  (L = 50 D)           |
| 6 | `meta.find_undeclared_variables` (Jinja's own) | O(B²)                                           | B sibling `{% if %}` blocks — **one axis only** | n^1.88 → 2.04             | n/a                          |

Rows 1–5 each need *thousands* of tags, unclosed `{#`, or unclosed delimiters in a single document
before they cost anything.

Row 6 is the only genuinely quadratic one, and it is inside Jinja rather than in this package.
`meta.find_undeclared_variables` is quadratic in the number of sibling `{% if %}` blocks: the local
slope climbs 1.88 → 1.90 → 1.96 → 2.04, and a control run with the same node count and no `{% if %}`
blocks is exactly linear (n^1.00 over the same range), which pins the cause to the blocks rather than
to template size.

In practice this is theoretical. Real templates sit at the left end of that curve:

| B sibling `{% if %}` blocks | 25 | 100 | 500 | 2000 | 8000 |
| --------------------------- | --: | --: | --: | ---: | ---: |
| `find_undeclared_variables` | 0.7 ms | 3 ms | 38 ms | 533 ms | 8.5 s |

A document with 100 conditional blocks is already an unusually elaborate template, and it costs 3 ms.
The quadratic is real and worth knowing before someone generates templates programmatically, but it is
not a cost anyone hand-authoring in Word will reach. Nothing here can avoid it either way — Jinja is
what decides which names a template actually requires.

</details>

## Known limitations

- **Arithmetic and filters do not inform the type.** `{{ v + 1 }}`, `{{ v * 2 }}`, `{{ v | int }}` and
  `{% if v > 5 %}` all report `v` as a string. The operator node is traversed through to reach the
  name beneath it, and nothing carries down what it was reached through. `NumberNode` exists in the
  model for this, and nothing produces it yet.
- **`{{ total-discount }}` warns even though it is valid subtraction**, because it is far more often
  a name someone meant to write with an underscore. Writing `{{ total - discount }}` clears it.
- **An unknown filter reports no variables.** Asking Jinja for the names compiles the template, so
  `{{ x | to_json }}` fails there rather than at parse time, and a caller may well register that
  filter later. The template comes back with zero variables and no warning.
- **A template that will not parse reports no variables.** Diagnostics explain why, but the author
  has to fix them before seeing any shape information.
- **Line numbers are lines of the extracted text**, not of the Word document, since the conversion to
  plain text loses formatting.
- **Two checks are line-scoped**, so a broken delimiter split across a newline is not reported.
  Well-formed tags are matched across lines; only the checks hunting *missing* delimiters work a line
  at a time, because a tag with no delimiters cannot be found as a tag.
- **A paragraph break inside a name hides the text checks.** `find_tags` folds the newline to a single
  space so the tag reads as one line, which rejoins a break at a token boundary
  (`{{ store⏎.items }}`) but not one inside a name (`{{ store.⏎items }}` folds to `store. items`, and
  the collision check no longer matches). Variable extraction is unaffected either way, since Jinja
  ignores whitespace inside a tag. Folding to nothing instead would fix this case and break
  `{% for r⏎in rows %}`, so the space is deliberate.
- **Tag style is not linted.** Spacing, casing and indentation inside tags are left alone on purpose:
  docx extraction produces enough incidental whitespace that style rules fire constantly on valid
  templates.

## Layout

Each `checks/` module is named for **what is wrong**, not for what it reads.

| file                    |                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------- |
| `types.py`              | the `VariableNode` union, `TemplateReport`, and every other shape the modules pass around — imports nothing from the package, so it can be imported anywhere |
| `analyze.py`            | `analyze_jinja_template()` — the entry point, and which warnings survive               |
| `variable_tree.py`      | `VariableTreeVisitor`, which subclasses Jinja's `NodeVisitor` and adds shape inference |
| `checks/delimiters.py`  | the braces are malformed, so Jinja never sees a tag at all                            |
| `checks/names.py`       | a name inside a tag will not resolve the way it is written                            |
| `checks/blocks.py`      | block structure is wrong — counts do not match, or a tag needs an enclosing loop      |
| `checks/parser.py`      | Jinja's own parse error, reworded                                                     |
| `checks/objects.py`     | an object or list is printed directly                                                 |
| `utils/ast_utils.py`    | reading a Jinja AST node                                                              |
| `utils/docxtpl_utils.py`| parsing, and rewriting docxtpl's tag syntax                                           |
| `utils/string_utils.py` | wording a warning, blanking out comments                                              |
| `utils/tag_utils.py`    | `TemplateText`, the views every check shares, including every Jinja tag in order       |
| `tests/`                | one file per check, one test per edge case, so a failure names the case that broke     |

[docxtpl]: https://docxtpl.readthedocs.io
[jinjaninja]: https://github.com/ramonsaraiva/jinjaninja
