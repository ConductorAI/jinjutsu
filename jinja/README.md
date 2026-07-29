# Jinja template analysis

Reads a Jinja template and answers two questions in one pass:

1. **What data does this template need?** Not just the variable names, but their shape — is
   `sections` a list of objects with a `title` field, or a list of strings? Jinja's own
   `meta.find_undeclared_variables` gives you names only.
2. **What is wrong with it?** In wording a non-programmer can act on, with a line number, the text
   that caused it, and the edit that fixes it.

Built for templates authored in Word and rendered with [docxtpl], so it understands docxtpl's tag
syntax and the mistakes Word introduces on its own (curly quotes, stray spaces inside tags).

## Usage

```python
from conduit.server.features.doj.templates.jinja import analyze_jinja_template

report = analyze_jinja_template(template_text)

report.variables    # {"case": {"type": "object", "properties": {...}}, ...}
report.diagnostics  # ["Line 2: ...", ...] — worded, ready to display
```

`analyze_jinja_template` parses once and hands the result to both halves. It never raises for a malformed
template — a parse failure comes back as a diagnostic.

```
Line 2: Field 'items' collides with a built-in method
  Found: {{ store.items }}
  Fix:   {{ store['items'] }}
  Reason: Jinja reads '.items' as the dictionary's own method, so the document renders the
          method instead of your value. Use bracket syntax.
```

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

Objects and lists are interior nodes; strings and booleans are leaves.

Two parts of the shape are easy to misread:

- **`properties` means one thing per type.** On an object it is that object's own fields. On a list
  it is the fields of *one element*, so `sections.properties.name` says every section has a name,
  never that the list itself has one. A loop is what puts it there: `{% for s in sections %}` binds
  `s` to the `sections` node, so `{{ s.name }}` writes `name` into that node's properties.
- **`item_format` says what one element of a list looks like.** It is filled in after the walk,
  derived from whether the list ended up with properties, so it carries nothing the tree does not
  already say. It is there for callers that want the answer without walking the tree themselves.

### How types are decided

| template | inferred |
|---|---|
| `{{ x }}` | `string` |
| `{% if x %}` | `boolean` — a guard, never rendered |
| `{% if x %}{{ x }}{% endif %}` | `string` — rendering pins it |
| `{% if x == true %}` | `boolean` |
| `{% if x == 'FINAL' %}`, `{% if x == 1 %}` | `string` |
| `{% if x %}{{ x.title }}{% endif %}` | `object` — the guard was an existence check |
| `{% for s in xs %}{{ s }}{% endfor %}` | `xs`: list of strings |
| `{% for s in xs %}{{ s.a }}{% endfor %}` | `xs`: list of objects |
| `{{ xs[0].a }}`, `{{ xs.0.a }}` | `xs`: list of objects |
| `{{ r['items'] }}` | `r`: object with an `items` field (string key, not an index) |

Names the template invents are never reported, since nobody supplies them: loop targets, `{% set %}`
targets, and macro, call and with block parameters.

## Warnings

`report.diagnostics` is a list of finished strings, ready to display. Three layouts, each built by
one helper:

`warning_to_string` in `jinja_utils.py` — most warnings, wherever there is a line to point at:

```
Line 4: 'a' is used as both a value and an object
  Found: a.b
  Fix:   give the two uses different names        <- three spaces, aligned
  Reason: ...                                    <- optional
  {{ a.b }}                                      <- optional source line
```

`_tag_count` in `checks/syntax.py` — a count that is wrong across the whole template, so there is no
one line to blame:

```
Mismatched loop tags
  Found: 1 {% for %} tag(s) but 0 {% endfor %} tag(s)
  Fix: Each {% for %} must have a corresponding {% endfor %}   <- one space
```

`_syntax_error` in `checks/syntax.py` — Jinja's own message, wrapped in friendlier guidance and kept
underneath:

```
Line 2: Unexpected 'b' after the expression
  {% if a b c %}
  Error: expected token 'end of statement block', got 'b'
```

## Why custom checks instead of Jinja's parser

Jinja's messages are written for programmers. `Encountered unknown tag 'endif'` on line 40 is a
useless thing to show someone whose real mistake was typing `{ % if x %}` on line 1. So the custom
checks run first and Jinja's parser is the fallback for anything they miss.

Suppression follows one rule: **a check silences Jinja's error only when both are looking at the
same mistake.**

- A **broken delimiter** silences it entirely. Jinja reads the tag as plain text, so every error
  after that is a consequence — it will blame an innocent end tag pages below. For the same reason
  the tag counts are suppressed too: they cannot see an opener they do not recognize, so they would
  claim zero `{% if %}` tags when one is sitting right there, just broken.
- A **tag-count mismatch** silences only Jinja's block-balance errors (`unexpected end of template`,
  `unknown tag 'end…'`), which restate the same imbalance less clearly. Any other Jinja error is an
  independent problem and is reported alongside.
- Everything else (hyphens, built-in method collisions, cell merges) never silences anything — none
  of them affects whether the template parses.

This matters: a mismatched tag used to hide a genuine expression error further down, so authors
fixed one problem and only then discovered the next.

## docxtpl support

docxtpl tags are rewritten to vanilla Jinja before parsing: the `tr`/`tc`/`p`/`r` row, cell,
paragraph and run prefixes are blanked, `{% vm %}` and `{% hm %}` cell merges are blanked, and
`{% colspan n %}` / `{% cellbg c %}` become `{{ n }}` / `{{ c }}`, the substitution docxtpl itself
performs.

**Every rewrite preserves character count and newline positions.** Whitespace inside a tag is
insignificant to Jinja, which is what leaves room to pad. Widening or narrowing the text would
silently shift every diagnostic after a docxtpl tag, and dropping a newline would shift every
diagnostic in the rest of the template.

## Known limitations

- **A 2D list is flattened.** `matrix[0][1]` has nowhere to go, because `item_format` is a flat enum
  rather than a recursive child. To express a grid, nest loops instead:
  `{% for row in table %}{% for cell in row.cells %}{{ cell }}{% endfor %}{% endfor %}`.
- **`{{ total-discount }}` warns even though it is valid subtraction**, because it is far more often
  a name someone meant to write with an underscore. Writing `{{ total - discount }}` clears it.
- **A template that will not parse reports no variables.** Diagnostics explain why, but the author
  has to fix them before seeing any shape information.
- **Line numbers are lines of the extracted text**, not of the Word document, since the conversion
  to plain text loses formatting.
- **Two checks are line-scoped**, so a broken delimiter split across a newline is not reported.
  Well-formed tags are matched across lines; only the checks hunting *missing* delimiters work a
  line at a time, because a tag with no delimiters cannot be found as a tag.

## Layout

| file | |
|---|---|
| `analysis.py` | `analyze_jinja_template()` and `TemplateReport` — the entry point, the walk that builds the tree, and which warnings survive |
| `variable_tree.py` | `VariableNode` and `VariableTreeVisitor`, which subclasses Jinja's `NodeVisitor` and adds shape inference |
| `checks/delimiters.py` | tags whose delimiters are broken, so Jinja never sees them as tags |
| `checks/tags.py` | what is written inside a well-formed tag |
| `checks/syntax.py` | block balance and Jinja's own parser |
| `checks/objects.py` | objects and lists printed whole, which only the finished tree reveals |
| `utils/ast_utils.py` | reading a Jinja AST node |
| `utils/docxtpl_utils.py` | parsing, and rewriting docxtpl's tag syntax |
| `utils/string_utils.py` | wording a warning, and blanking out comments |
| `tests/` | one test per edge case, so a failure names the case that broke |

`checks/` is split by **what each module reads** — raw lines, tag contents, the parser, or the
finished variable tree. That is also why `delimiters.py` works a line at a time and the others do
not.

[docxtpl]: https://docxtpl.readthedocs.io
