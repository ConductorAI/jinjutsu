# Jinjutsu

Our package analyzes a Jinja template and answers two questions:

1. **What data does this template need?** Not just the variable names, but also the expected types for each variable.
2. **What is wrong with it?** In plain language a non-programmer can act on, with a line number, the text that caused it, and a suggested fix.

## How does it compare with using Jinja directly?

Jinja's messages make it difficult to tell what's wrong or how to fix it, and they often blame the wrong line or include false positives. `Encountered unknown tag
'endif'` on line 40 is a useless thing to show someone whose real mistake was typing `{ % if x %}` on the first line. 

Jinja also doesn't warn on errors that are technically valid jinja, but likely to be wrong, such as printing a built in function (which renders as `<method 'index' of 'list' objects>`)
or having a variable name such as `pending-edits`, which renders as subtraction.

Measured against three hand-built suites: 21 valid templates that must not be flagged, 29 with real
breakage, and 10 that parse cleanly but render wrong.

|                  | valid templates falsely flagged | real breakage caught | semantic gotchas caught |
| ---------------- | ------------------------------: | -------------------: | ----------------------: |
| **This package** |                        **0/21** |            **28/29** |                **8/10** |
| Plain Jinja      |                            4/21 |                24/29 |                    0/10 |
| [jinjaninja]     |                            4/21 |                 4/29 |                    0/10 |


In fairness to [jinjaninja], it bills itself as a style enforcement tool, so correctness cases are
not what it set out to catch but we're including it in the table because it is the closest package to a Jinja validator that exists today.

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
| Unknown filter (`{{ x \| to_json }}`)                              | ✅ names the filter, suggests `tojson`      | ❌                                      | ❌                   |
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

The same analysis is available as a command, with an exit code a CI job or a pre-commit hook can read:

```sh
jinjutsu NAME_OF_TEMPLATE_FILE.txt [--warnings] [--tree] [--schema] [--all]
```

See [examples/cli](examples/cli) for what each flag prints.

## Examples

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

All fields will be optional by default, since the render can always succeed with missing variables (based on default jinja env settings)

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
| `{{ x - 1 }}`, `{{ x / 2 }}`, `{{ x ** 2 }}`, `{{ -x }}` | `number` since a string cannot survive this |
| `{{ x * y }}`, `{{ x * 2 }}`, `{{ '-' * x }}` | `number` — `"a" * "b"` raises, so a side always counts |
| `{{ x + 1 }}`, `{{ x % 2 }}`               | `number` — the literal says which meaning        |
| `{{ x + y }}`, `{{ x % y }}`, `{{ x ~ y }}` | `string` — as likely concat or printf           |
| `{% if x > 5 %}`, `{% if 5 < x %}`          | `number`                                        |
| `{% if x > y %}`, `{% if x > 'm' %}`        | `string` — strings compare lexicographically    |
| `{% if x %}{{ x.title }}{% endif %}`        | `object` — the guard was an existence check     |
| `{% for s in xs %}{{ s }}{% endfor %}`      | `xs`: list of strings                           |
| `{% for s in xs %}{{ s.a }}{% endfor %}`    | `xs`: list of objects                           |
| `{{ xs[0].a }}`, `{{ xs.0.a }}`             | `xs`: list of objects                           |
| `{{ m[0][1] }}`                             | `m`: list of lists of strings                   |
| `{% for f in fs %}{% if f %}{% endif %}{% endfor %}` | `fs`: list of booleans                 |
| `{% for x in xs %}body{% endfor %}`         | `xs`: list of strings                           |
| `{{ r['items'] }}`                          | `r`: object with an `items` field.              |

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

### Which warnings survive?

The custom checks run first, and Jinja's parser is the fallback for anything they miss. Warnings from our custom checker silence Jinja errors only when both are looking at the same mistake.

- A **broken delimiter** silences Jinja errors entirely. Jinja reads the tag as plain text, so every error is based on an incorrect assumption.
- A **tag-count mismatch** silences Jinja's block-balance errors (such as`unexpected end of template`, `unknown tag 'end…'`) which would just restate the same issues less clearly.
- All other errors (hyphens, built-in method collisions, cell merges) don't silence anything, since these don't affect whether the template parses.

This is a big UX improvement from the Jinja-only workflow, since previously a mismatched tag would hide a genuine expression error further down, so author would fixe one problem and only then discover the next.

## Support for `docxtpl`

If you're not working with docx files then this section is irrelevant, and you don't need to know what docxtpl is. If you are and would like to render custom Word elements such as tables based on template values, read more about how to do this with docxtpl here: https://docxtpl.readthedocs.io/en/latest/

As a quick primer, docxtpl is effectively a layer built on top of Jinja. Jinja does all the rendering while docxtpl gets the text into and out of the `.docx`. In addition to your own Jinja tags you
get a handful of built-in **tag prefixes** such as `tr` and `tc`, which tell docxtpl when to render a new table row or cell

**Word documents can be passed directly, but we only analyze the extracted text.** The CLI extracts the document's template text itself (including from paragraphs,
tables, headers, footers and textboxes) in document order and analyzes that. When using programmatically on a local Word file we'd need to call `extract_docx_text` to get the document text before running it through our variable parser like so:

```python
from jinjutsu import analyze_jinja_template, extract_docx_text

report = analyze_jinja_template(extract_docx_text("invoice.docx"))
```

### What a docxtpl workflow looks like end to end:

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

Note that these tags `tr` are not generated by docxptl or some type of docx conversion script, they're manually added by humans building template files that they want rendered into docx.

Without docxtpl support, Jinja rejects `{%tr %}` as an unknown tag, a parse failure occurs, and the author would be told their correctly written template is broken:

```
Line 2: Check for typos or formatting issues
  {%tr for line in invoice.lines %}
  Error: Encountered unknown tag 'tr'.
```

With it, the prefixes are removed before parsing and the correct variable tree is returned:

```
invoice         object
|-- number      string
|-- lines       list of objects
|   |-- desc    string
|   `-- amount  string
`-- paid        boolean
```

Rendered with a context, the finished document might look like:

```
Invoice INV-0042
Design       $1,200.00
Development  $3,400.00
PAID
```

See [examples/docx](examples/docx) for runnable scripts to test out this workflow.

## Performance

<details>
<summary><b>TLDR: don't worry about it</b></summary>

One full `analyze_jinja_template` call against random test documents with the following attributes, recording the best of 3 runs.
These ratios are meaningful even though the absolute numbers might vary in different environments:

| shape (chars, lines)                                            | this package |  jinjaninja |
| --------------------------------------------------------------- | -----------: | ----------: |
| 100 pg prose, 6 tags (301 KB, 750 lines)                        |        23 ms |        5 ms |
| 500 pg prose, 6 tags (1.5 MB, 3750 lines)                       |       111 ms |       26 ms |
| 500 pg, 6 tags, prose with `100%` and `{see Exhibit C, § 4(b)}` |       115 ms |       28 ms |
| 1000 pg prose, 6 tags (3.0 MB)                                  |       220 ms |       52 ms |
| 500 pg prose, 600 tags                                          |       716 ms |     1343 ms |
| 500 pg, 6 tags, one long line — tags at the end                 |        97 ms |       21 ms |
| 500 pg, 6 tags, one long line — tags spread through it          |       114 ms | **19349 ms** |

On most normal docs the jinjaninja linter is 4× quicker, but at these magnitudes neither number
matters. Two takeaways of note:

- **Cost tracks the number of tags, not document length.** 600 tags in 1.5 MB costs more than 6 tags in 3.0 MB.
- **A docx that extracts to one unbroken line is rare but a trap for jinjaninja's regex implementation.** jinjaninja goes from 21 ms to 19 seconds on the same number of bytes
depending on whether we have line breaks because its regexes use a greedy `(.+\w+)?` that backtracks across content following a tag.

</details>

<details>
<summary><b>Where the costs are</b></summary>

**An axis is one thing you can make bigger about a template.** Every cost below is a product of two
of them, so each row names its own pair. For example `find_tags` costs tags × bytes, and a template with many tags *and* many bytes is what makes it expensive.



| # | site                                           | runtime complexity                              | axes (A, B)                              | 
| - | ---------------------------------------------- | ----------------------------------------------- | ---------------------------------------- | 
| 1 | `find_tags` line numbering                     | O(M × N)                                        | M tags, N bytes                          |
| 2 | `warning_to_string(source_line=)`              | O(W × L)                                        | W warnings, L embedded line length       |
| 3 | `replace_comments_with_spaces`                 | O(C × N)                                        | C unclosed `{#`, N bytes                 |
| 4 | `check_malformed_tags` regexes                 | O(D × L)                                        | D unclosed delimiters, L line length     | 
| 5 | `meta.find_undeclared_variables` (Jinja's own) | O(B²)                                           | B sibling `{% if %}` blocks — **one axis only** |

Rows 1–4 each need *thousands* of tags, unclosed `{#`, or unclosed delimiters in a single document (which will be extremely rare) before they cost anything.

Row 5 is the only quadratic one, and it is inside Jinja rather than in this package.
`meta.find_undeclared_variables` is quadratic in the number of sibling `{% if %}` blocks rather than the full template size.

In practice this is theoretical. 

| B sibling `{% if %}` blocks | 25 | 100 | 500 | 2000 | 8000 |
| --------------------------- | --: | --: | --: | ---: | ---: |
| `find_undeclared_variables` | 0.7 ms | 3 ms | 38 ms | 533 ms | 8.5 s |

A document with 100 conditional blocks is already an unusually elaborate template, and it costs 3 ms.
The time complexity is worth knowing if we're generating templates programmatically, but likely not a problem for any handwritten template would run in.
Nothing here can avoid it either way since Jinja is what decides which names a template actually requires.

</details>

## Debugging

Known limitations, ordered by most to least likely to be encountered:

- **Line numbers are lines of the extracted text, not the Word document** This is because the conversion to plain text loses formatting.
- **An unevidenced shape is reported as `string`.** A Jinja variable with no operations on it other than a render is serialized to a string type, which is a default rather than a finding. This is likely one of the higher priority issues we need to address before we add the ability to validate context.
- **Nothing is marked required.** This is hard to determine. Also having all variables be optional is the best approach here philosophically since the template can still successfully render with missing variables.
- **Default values aren't read.** `{{ name | default("friend") }}` parses and yields the right type, but there might be conflicting defaults for the same variable throughout the document.
- **Filters aren't factored when deciding on the type.** This wouldn't be reliable for now since an object can have a lot of filters that imply different types, including custom filters defined in the user's Jinja environments
- **`{% if x == 1 %}` reports `string`, but `{% if x > 1 %}` reports `number`.** The equality check gets ignored since it isn't as strong of a signal as the > comparison, and we go with number as the final type.
- **`{{ pending-edits }}` warns even though it is valid subtraction.** Most likely that someone meant to type a variable with an underscore. Changing the text to `{{ pending - edits }}` with spacing clears it.
- **Some checks are line-scoped.** A broken delimiter split across a newline might not be reported.
- **No lint checks on spacing.** Docx extraction will produce enough random whitespace that style rules would fire constantly on valid templates.


## Resources

- [jinja][jinja] — The syntax we're checking formatting on and rendering variables for. This is a must read
- [docxtpl][docxtpl] — Syntax for rendering a Word document as a Jinja template. Covers the specific tags used to render different Word elements and everything else the
  [docxtpl support](#support-for-docxtpl) section summarizes.
- [jinjaninja][jinjaninja] — The Jinja style linter benchmarked in the
  [comparison above](#how-does-it-compare-with-using-jinja-directly).

[jinja]: https://jinja.palletsprojects.com/en/stable/templates/
[docxtpl]: https://docxtpl.readthedocs.io
[jinjaninja]: https://github.com/ramonsaraiva/jinjaninja
