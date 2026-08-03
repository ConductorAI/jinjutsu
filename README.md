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

## Why not just use Jinja's parser?

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

<details>
<summary><b>Full case-by-case comparison</b> (38 cases)</summary>

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
| Unknown filter (`{{ x \| to_json }}`)                              | ❌ zero variables, other warnings still made | ❌                                      | ❌                   |
| **docxtpl-specific**                                               |                                             |                                         |                      |
| `{%tr %}` / `{%p %}` / `{{r }}` prefixed tags                      | ✅ correctly ignored                        | ❌ false positive — unknown tag `'tr'`  | ❌ false positive    |
| `{% vm %}` `{% hm %}` `{% colspan n %}` `{% cellbg c %}`, used well | ✅ ignored, arguments extracted             | ❌ false positive — unknown tag `'tr'`  | ❌ false positive    |
| `{% cellbg %}` with no argument                                    | ⚠️ generic                                   | ⚠️ unknown tag `'cellbg'`                | ❌                   |
| `{% vm %}` / `{% hm %}` outside a loop                             | ✅ names the tag and the fix                | ⚠️ unknown tag `'vm'`                    | ❌                   |
| Two prefixed tags in one paragraph / row / cell                    | ✅ names the element and the fix             | ⚠️ unknown tag `'p'` — the prefix, not the clash | ❌                   |
| Prefixed tag beside text in one element — renders, content lost     | ✅ names what gets deleted                   | ⚠️ unknown tag `'p'` — the prefix, not the loss | ❌                   |
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

report.schema       # dict — JSON Schema for the context the template expects
report.diagnostics  # list[str] — formatted strings, ready to show the user
```

`analyze_jinja_template` parses once and shares that result between the two passes: the AST walk in
`variable_tree.py` and the text checks in `checks/`. It never raises for a malformed template — a
parse failure comes back as a diagnostic.

The same analysis is available as a command, with an exit code a CI job or a pre-commit hook can read:

```sh
jinjutsu TEMPLATE [TEMPLATE ...] [--warnings] [--tree] [--schema] [--all]
```

See [examples/cli](examples/cli) for what each flag prints.

## Schema

`report.schema` is a JSON Schema for the context object the template expects. Given:

```jinja
{{ case.header.title }}
{% for s in case.sections %}{{ s.name }}{% endfor %}
{% if case.sealed %}SEALED{% endif %}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "case": {
      "type": "object",
      "properties": {
        "header": {"type": "object", "properties": {"title": {"type": "string"}}},
        "sections": {
          "type": "array",
          "items": {"type": "object", "properties": {"name": {"type": "string"}}}
        },
        "sealed": {"type": "boolean"}
      }
    }
  }
}
```

The CLI prints the same thing as a tree:

```
case           object
|-- header     object
|   `-- title  string
|-- sections   list of objects
|   `-- name   string           a field on each section, not on the list
`-- sealed     boolean
```

Three things are worth knowing:

- **A list describes its element under `items`.** `sections.items` is the shape of one section, so
  `sections.items.properties.name` says every section has a name, never that the list itself has one.
  A loop is what puts it there: `{% for s in sections %}` binds `s` to the element of `sections`, so
  `{{ s.name }}` writes `name` into that element. Nested lists nest their `items`, so `{{ m[0][1] }}`
  gives `array` of `array` of `string`.
- **`required` is never emitted, so every field is optional.** See the limitation below — the schema
  describes shapes, not obligations. Top-level properties are sorted, which keeps the output stable
  enough to commit and diff.
- **`additionalProperties` is not set.** A real context usually carries more than one template reads,
  and rejecting that would make the schema useless for validating the data you already have.

Internally the walk builds a tagged union of node dataclasses — `ObjectNode`, `ListNode`,
`StringNode`, `BooleanNode`, `NumberNode`, `UnknownNode`, discriminated on `kind`. That model is an
implementation detail of `types.py` and is not exported; `schema.py` is the only thing that reads it.

### How types are decided

<details>
<summary><b>The full inference table</b> (one row per pattern)</summary>

| template                                    | inferred                                        |
| ------------------------------------------- | ----------------------------------------------- |
| `{{ x }}`                                   | `string`                                        |
| `{% if x %}`                                | `boolean` — a guard, never rendered             |
| `{% if x %}{{ x }}{% endif %}`              | `string` — rendering pins it                    |
| `{% if x == true %}`                        | `boolean`                                       |
| `{% if x == 'FINAL' %}`, `{% if x == 1 %}`  | `string`                                        |
| `{{ x - 1 }}`, `{{ x / 2 }}`, `{{ x ** 2 }}`, `{{ -x }}` | `number` — a string cannot survive these |
| `{{ x * y }}`, `{{ x * 2 }}`, `{{ '-' * x }}` | `number` — `"a" * "b"` raises, so a side always counts |
| `{{ x + 1 }}`, `{{ x % 2 }}`               | `number` — the literal says which meaning       |
| `{{ x + y }}`, `{{ x % y }}`, `{{ x ~ y }}` | `string` — as likely concat or printf           |
| `{% if x > 5 %}`, `{% if 5 < x %}`          | `number`                                        |
| `{% if x > y %}`, `{% if x > 'm' %}`        | `string` — strings compare lexicographically    |
| `{% if x %}{{ x.title }}{% endif %}`        | `object` — the guard was an existence check     |
| `{% for s in xs %}{{ s }}{% endfor %}`      | `xs`: list of strings                           |
| `{% for s in xs %}{{ s.a }}{% endfor %}`    | `xs`: list of objects                           |
| `{{ xs[0].a }}`, `{{ xs.0.a }}`             | `xs`: list of objects                           |
| `{{ m[0][1] }}`                             | `m`: list of lists of strings                   |
| `{% for f in fs %}{% if f %}{% endif %}{% endfor %}` | `fs`: list of booleans                 |
| `{% for x in xs %}body{% endfor %}`         | `xs`: list of strings — nothing reads the element |
| `{{ r['items'] }}`                          | `r`: object with an `items` field, not an index  |

Names the template invents are never reported, since nobody supplies them: loop targets,
`{% set %}` targets, and macro, call and with block parameters.

</details>

## Diagnostics

`report.diagnostics` is a list of formatted strings you can show the user directly. Some examples of possible warnings:

```
Mismatched loop tags
  Found: 1 {% for %} tag(s) but 0 {% endfor %} tag(s)
  Fix:   Each {% for %} must have a corresponding {% endfor %}
```

```
Line 2: Unexpected 'b' after the expression. The tag holds one expression, nothing more
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

## Support for `docxtpl`

If you're not working with docx files then this section is irrelevant, and you don't need to know what docxtpl is. If you are and would like to render custom Word elements such as tables based on template values, read more about how to do this with docxtpl here: https://docxtpl.readthedocs.io/en/latest/

As a quick primer, docxtpl is effectively a layer built on top of jinja — jinja does all the
rendering, docxtpl gets the text into and out of the `.docx`. In addition to your own jinja tags you
get a handful of built-in **tag prefixes** such as `tr` and `tc`, which tell docxtpl that a tag
governs the table row or cell around it rather than just the text between the braces.

**A `.docx` can be passed directly.** The CLI extracts the document's template text itself — paragraphs,
tables, headers, footers and textboxes, in document order — and analyzes that. As a library the same
extraction is one call away:

```python
from jinjutsu import analyze_jinja_template, extract_docx_text

report = analyze_jinja_template(extract_docx_text("invoice.docx"))
```

### What that buys, end to end

A human author writes `invoice.docx` in Word. Here `{%tr %}` is the docxtpl prefix that makes the loop repeat the whole table row, and `{%p %}` makes the condition govern whole paragraphs:

```
Invoice {{ invoice.number }}
{%tr for line in invoice.lines %}
{{r line.desc }} {{ line.amount }}
{%tr endfor %}
{%p if invoice.paid %}
PAID
{%p endif %}
```

**Without docxtpl support**, Jinja rejects `{%tr %}` as an unknown tag, and a parse failure means no shapes at all. The author is told their correctly written template is broken:

```
Line 2: Check for typos or formatting issues
  {%tr for line in invoice.lines %}
  Error: Encountered unknown tag 'tr'.
```

**With it**, the prefixes are blanked before parsing and the real answer comes back:

```
invoice         object
|-- number      string
|-- lines       list of objects
|   |-- desc    string
|   `-- amount  string
`-- paid        boolean
```

No warnings, since nothing is wrong with the template. `lines` is a list of objects because
`{%tr for %}` is a loop once the prefix is gone, and `paid` is a boolean because `{%p if %}` is a
truthiness test. Both facts are unreachable if the parse fails.

Hand docxtpl a context of that shape and the finished document reads:

```
Invoice INV-0042
Design       $1,200.00
Development  $3,400.00
PAID
```

One real table row per line item, the tag-only rows gone, and `PAID` there because `paid` was true. See
[examples/docx](examples/docx) for the whole workflow as runnable scripts — checking a document, then rendering it with docxtpl, plus info about the prefixes in more detail.

## Performance

<details>
<summary><b>TLDR: don't worry about it</b></summary>

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

</details>

<details>
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
| 3 | `replace_comments_with_spaces`                 | O(C × N)                                        | C unclosed `{#`, N bytes                 | n^1.01 opens, n^1.02 bytes      | n^2.02  (N = 500 C)          |
| 4 | `check_malformed_tags` regexes                 | O(D × L)                                        | D unclosed delimiters, L line length     | n^0.96 opens, n^0.98 length     | n^1.94  (L = 50 D)           |
| 5 | `meta.find_undeclared_variables` (Jinja's own) | O(B²)                                           | B sibling `{% if %}` blocks — **one axis only** | n^1.88 → 2.04             | n/a                          |

Rows 1–4 each need *thousands* of tags, unclosed `{#`, or unclosed delimiters in a single document
before they cost anything.

Row 5 is the only genuinely quadratic one, and it is inside Jinja rather than in this package.
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

## Debugging

Known limitations, ordered by most to least likely to be encountered:

- **A template that will not parse reports no variables.** Diagnostics explain why, but the author has to fix them before seeing any shape information.
- **Line numbers are lines of the extracted text**, not of the Word document, since the conversion to plain text loses formatting.
- **An unevidenced shape is reported as `string`.** A name jinja requires that the walk never shaped serializes as `{"type": "string"}`, which is a default rather than a finding. Validating a context that supplies a number might fail.
- **Nothing is marked required, on purpose.** Whether a name may be absent is a property of each
  *place* it is used, not of the name: `{{ name | default("x") }}{{ name }}` is optional at one site and mandatory at the other, and a single flag per name cannot say both. It also depends on the renderer — under `StrictUndefined` even `{% if v %}` raises, so nothing is ever safely absent.
  Until usage sites are modelled the schema omits `required`, which in JSON Schema means no
  obligations rather than an empty set of them.
- **Default values aren't read.** `{{ name | default("friend") }}`, `{% if name is defined %}`
  and `{{ name or "friend" }}` all parse and yield the right *shape*, but there can be conflicting filters throughout the document, as well as custom user defined filters in the jinja env that we don't parse.
- **Filters don't inform the type.** `{{ v | int }}` reports `v` as a string, because the filter wrapper is traversed through to reach the name beneath it and nothing carries down what it was reached through. Arithmetic *is* read this way; filters are the remaining case, and they need a decision first — `| int` suggests the value arrives as a string needing coercion, and `| length` makes the *expression* a number while the name stays a list.
- **An unknown filter reports no variables.** Asking Jinja for the names compiles the template, so
  `{{ x | to_json }}` fails there rather than at parse time, and a caller may well register that
  filter later. The template comes back with zero variables, though the warnings that do not depend
  on those names — a printed object, a name used as both a value and an object — are still reported.
- **`{% if x == 1 %}` reports `string`, but `{% if x > 1 %}` reports `number`.** Equality is ignored since it is less of a signal than the > comparision, so we go with number as the final type.
- **`{{ total-discount }}` warns even though it is valid subtraction**, because it is far more often a name someone meant to write with an underscore. Writing `{{ total - discount }}` clears it.
- **Some checks are line-scoped**, so a broken delimiter split across a newline might not be reported.
- **No lint checks on spacing.** Spacing, casing and indentation inside tags are left alone on purpose since docx extraction will produce enough random whitespace that style rules would fire constantly on valid templates.


## Resources

- [jinja][jinja] — The syntax template authors write: tags, filters, tests and expressions. What this package parses, and what its diagnostics teach.
- [docxtpl][docxtpl] — Syntax for rendering a Word document as a Jinja template. Covers the specific tags used to render Word elements and everything else the
  [docxtpl support](#support-for-docxtpl) section summarizes.
- [jinjaninja][jinjaninja] — The Jinja style linter benchmarked in the
  [comparison above](#why-not-just-use-jinjas-parser).

[jinja]: https://jinja.palletsprojects.com/en/stable/templates/
[docxtpl]: https://docxtpl.readthedocs.io
[jinjaninja]: https://github.com/ramonsaraiva/jinjaninja
