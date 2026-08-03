# docxtpl, end to end

[docxtpl] (installed as `docxtpl`, on PyPI as `python-docx-template`) renders a Word document as a
Jinja template. You author a `.docx` in Word with Jinja tags typed into the text, call
`render(context)` with your data, and get back a finished `.docx` with every style, font, table and
header intact — only the tags are replaced.

This directory is the whole workflow, runnable: check a template with jinjutsu, then render it with
docxtpl. All commands run from the repo root, and `uv sync` installs what they need.

`samples/` holds two Word templates to run against. `invoice.docx` is correct — a `{%tr %}` loop in a
table and a `{%p if %}` block. `client.docx` has a real mistake, `{{ client.items }}` colliding with a
built-in method.

| step                     | takes            |                                                     |
| ------------------------ | ---------------- | --------------------------------------------------- |
| `step1_extract_text.py`  | a `.docx`        | prints its template text, walking paragraphs **and** tables in order |
| `step2_analyze.py`       | a `.docx`        | extract + analyze in one call — the diagnostics and the schema |
| `step3_render.py`        | a `.docx`        | renders it with docxtpl to `<name>_rendered.docx`     |

Each step takes the file to work on, so point them at either sample:

```sh
$ uv sync
$ uv run python examples/docx/step1_extract_text.py examples/docx/samples/invoice.docx
$ uv run python examples/docx/step2_analyze.py examples/docx/samples/invoice.docx
$ uv run python examples/docx/step3_render.py examples/docx/samples/invoice.docx
```

Swap in `client.docx` to watch step 2 report a real mistake — that is the only difference between the
two runs. Only `step1_extract_text.py` guards its body with `if __name__ == "__main__"`, because step 2
imports it; the other two run top to bottom.

## How docxtpl works

A `.docx` is a zip archive whose body is one XML file, `word/document.xml`. Text lives in **runs**
(`<w:r>`, a span of identically-formatted characters) inside **paragraphs** (`<w:p>`); a table is
rows (`<w:tr>`) of cells (`<w:tc>`) of paragraphs. When you call `render`, docxtpl patches that XML —
Word splits typed text across runs unpredictably, so a tag you typed as one piece may be scattered
over several, and docxtpl reunites them — then runs the patched XML through Jinja and saves the
result as a new document.

That design forces one extension to Jinja. A `{% for %}` you type into a table cell is just *text in
one cell* — looping it repeats the text, not the row it sits in. So docxtpl adds **prefixed tags**
that widen a tag's reach to the XML element around it:

| tag        | replaces the enclosing | typical use                                      |
| ---------- | ---------------------- | ------------------------------------------------ |
| `{%p %}`   | paragraph              | `{%p if %}` — a paragraph that appears conditionally |
| `{%tr %}`  | table row              | `{%tr for %}` — one table row per list element   |
| `{%tc %}`  | table cell             | `{%tc for %}` — one column per list element      |
| `{%r %}`   | run                    | statement scoped to a span of text               |
| `{{r }}`   | run                    | a [RichText] value — formatting decided by the data |

Everything typed in Word already sits in a paragraph, so `{%p %}` is not there to say *what* the
element is — it says **delete the paragraph, not just the text between the braces**. Jinja only
removes characters, so a plain `{% if %}` empties the `<w:p>` that held the tag but leaves it behind
as a blank line, whether the condition passed or not:

```
                        rendered paragraphs
{% if show %}    True   ['Before', '', 'Body', '', 'After']   <- a blank line per tag
{%p if show %}   True   ['Before', 'Body', 'After']
{% if show %}    False  ['Before', '', 'After']               <- still a blank line
{%p if show %}   False  ['Before', 'After']
```

`{%tr %}`, `{%tc %}` and `{%r %}` do the same for a row, a cell and a run.

Plus four table-formatting tags with no vanilla-Jinja equivalent: `{% colspan n %}` and
`{% cellbg color %}` substitute their argument from the context, `{% vm %}` and `{% hm %}` merge
cells vertically and horizontally.

**The placement rule:** a prefixed statement tag must sit **alone** in the element it names — one
`{%p %}` alone in its paragraph, one `{%tr %}` alone in its row, one `{%tc %}` alone in its cell.
docxtpl replaces that entire element with the bare tag, so whatever else was in there is deleted.

The patched XML makes it plain. Two paragraphs each become their own bare tag; one paragraph holding
both collapses to a single tag, and the `if` is simply gone:

```
{%p if show %}BODY   +   {%p endif %}     two paragraphs  ->  {% if show %}{% endif %}
{%p if show %}BODY{%p endif %}            one paragraph   ->  {% endif %}
```

Breaking the rule fails two different ways, and the quiet one is worse. `¶` is a new paragraph, `|` the
next cell. Rendered with `show` true, `Before` and `After` around the block:

```
p    {%p if show %} ¶ BODY ¶ {%p endif %}    one tag per paragraph   ['Before', 'BODY', 'After']
p    {%p if show %}BODY ¶ {%p endif %}       tag beside text         ['Before', 'After']   BODY gone
p    {%p if show %}BODY{%p endif %}          two tags, one paragraph  render error: unknown tag 'endif'

tr   {%tr for %} alone in its row            one tag per row         [['x', 'amt']]
tr   {%tr for %} | Amount  (same row)        tag beside a cell       [['x', 'amt']]   Amount gone
tr   {%tr for %} | {%tr endfor %} (same row) two tags, one row       render error: unknown tag 'endfor'

tc   {%tc for %} | {{ c }} | {%tc endfor %}  one tag per cell        [['a']]
tc   {%tc for %}HDR  (same cell)             tag beside text         [['a']]   HDR gone
tc   {%tc for %}{{ c }}{%tc endfor %}        two tags, one cell      render error: unknown tag 'endfor'
```

Each group is: correct, silently lossy, then a hard error.

jinjutsu reports both failure rows: `Two 'p' tags in one paragraph` for the error, and
`'p' tag shares its paragraph with other content` for the silent one, which no render would ever tell
you about. In the extracted text a row is one line and a cell is one tab-separated field, which is how
the check tells these apart. `{%r %}` is exempt: a run is a span *inside* a paragraph, so two of them
share a line safely.

This example originally had `{%p if invoice.paid %}PAID{%p endif %}` in a single paragraph and died
with `Encountered unknown tag 'endif'`. The fix is three paragraphs: the `{%p if %}`, the `PAID`, the
`{%p endif %}`.

Similarly, `{{r }}` replaces its run's XML with the value's XML, so it needs a `RichText` object — a
plain string there disappears silently from the rendered document. Use plain `{{ }}` for plain
strings.

### Table headers

A header row needs no tag at all. Only the rows *between* `{%tr for %}` and `{%tr endfor %}` repeat,
so an ordinary row above the loop renders once:

```
| Description               | Amount            |   <- ordinary row, no tag
| {%tr for line in lines %} |                   |
| {{ line.desc }}           | {{ line.amount }} |
| {%tr endfor %}            |                   |
```

```
2 lines  ->  [['Description', 'Amount'], ['Design', '$1,200.00'], ['Development', '$3,400.00']]
empty    ->  [['Description', 'Amount']]
```

An empty list therefore leaves the header stranded over an empty table. If that should vanish too,
wrap it in `{%tr if %}` — the same prefix, doing for the header what `{%tr for %}` does for the body:

```
| {%tr if lines %}          |                   |
| Description               | Amount            |
| {%tr endif %}             |                   |
| {%tr for line in lines %} |                   |
| {{ line.desc }}           | {{ line.amount }} |
| {%tr endfor %}            |                   |
```

```
2 lines  ->  [['Description', 'Amount'], ['Design', '$1,200.00'], ['Development', '$3,400.00']]
empty    ->  []
```

`invoice.docx` here has no header row, so its table is the first shape with the header line removed.

## 1. Check it before rendering

**jinjutsu needs only the text; docxtpl needs the document.** The two halves of this workflow want
different things, and it is worth being clear about why:

- **Analysis reads tags, and a tag is plain text.** Whether `invoice.lines` is a list of objects is
  decided entirely by the characters `{%tr for line in invoice.lines %}`. Fonts, styles and table
  borders say nothing about the shape of the context, so extracted text is all jinjutsu ever needs —
  and a `.docx` is not an input to it at all.
- **Rendering has to produce a Word file, so the formatting *is* the payload.** docxtpl does not
  discard the styles, tables, headers and images — it carries every one of them through to the output
  and substitutes only the tags. Hand it text and there would be nothing to build a document from.
  `{%tr for %}` would also have no `<w:tr>` element to repeat, and `{{r }}` no run to replace.

So the steps below feed jinjutsu *text*, while [step 3](#2-render-it) hands docxtpl the original
`.docx`. Pointing the CLI at the document instead is the common slip, and it says so:

```sh
$ jinjutsu examples/docx/samples/invoice.docx
Error: examples/docx/samples/invoice.docx
  Problem: Not a text file
  Fix:     Extract the document's text and pass that
  Reason:  A .docx is a zip archive, so there is no text to read here.
```

So extract the text first:

```sh
$ uv run --with python-docx python examples/docx/step1_extract_text.py examples/docx/samples/invoice.docx
Invoice {{ invoice.number }}
{%tr for line in invoice.lines %}
{{r line.desc }}	{{ line.amount }}
{%tr endfor %}
{%p if invoice.paid %}
PAID
{%p endif %}
```

**Walk tables, not just paragraphs.** The obvious one-liner —
`"\n".join(p.text for p in doc.paragraphs)` — reads only top-level paragraphs, and as the table
above shows, docxtpl's loops live inside table cells. On this very document it silently drops the
loop, and `invoice.lines` never appears in the schema:

```sh
$ uv run --with python-docx python -c "
from docx import Document
print('\n'.join(p.text for p in Document('examples/docx/samples/invoice.docx').paragraphs))"
Invoice {{ invoice.number }}
{%p if invoice.paid %}
PAID
{%p endif %}
```

`step1_extract_text.py` uses `Document.iter_inner_content()` instead, which yields paragraphs and tables
in document order, and joins each table row's cells with a tab — whitespace is insignificant inside
a Jinja tag, and one row per line keeps the reported line numbers pointing at the right row.

Now analyze — pass the text to the CLI, or redirect to a file for CI:

```sh
$ text="$(uv run --with python-docx python examples/docx/step1_extract_text.py examples/docx/samples/invoice.docx)"
$ jinjutsu "$text"
invoice         object
|-- number      string
|-- lines       list of objects
|   |-- desc    string
|   `-- amount  string
`-- paid        boolean
```

No warnings, and the tree is the context to build: `lines` is a list of objects because `{%tr for %}`
is a loop once the prefix is blanked, `paid` is a boolean because `{%p if %}` is a truthiness test.
The same pipeline on `client.docx` exits 1 and names its mistake:

```sh
$ text="$(uv run --with python-docx python examples/docx/step1_extract_text.py examples/docx/samples/client.docx)"
$ jinjutsu "$text"
===== warnings =================================================
Line 2: Field 'items' collides with a built-in method
  Found: {{ client.items }}
  Fix:   {{ client['items'] }}
  Reason: Jinja reads '.items' as the value's own method, so the document renders the method instead of your value. Use bracket syntax.
  Your order: {{ client.items }}

===== tree =====================================================
client     object
|-- name   string
`-- items  string
```

Line 2 is a line of the *extracted text*, not of the Word document — formatting is gone by the time
there are lines to count. `step2_analyze.py` is the same check as a library call, printing the
diagnostics and the JSON Schema.

## 2. Render it

`step3_render.py` builds the context the tree above describes and hands it to docxtpl:

```python
context = {
    "invoice": {
        "number": "INV-0042",
        "lines": [
            {"desc": RichText("Design", bold=True), "amount": "$1,200.00"},
            {"desc": RichText("Development"), "amount": "$3,400.00"},
        ],
        "paid": True,
    }
}

template = DocxTemplate(CURRENT_DIR / "invoice.docx")
template.render(context)
template.save(CURRENT_DIR / "invoice_rendered.docx")
```

`desc` is a `RichText` because the template reads it with `{{r }}` — the first line renders bold
because the *data* says so, formatting no template edit could express. Run it and read the result
back with the same extractor:

```sh
$ uv run --with docxtpl python examples/docx/step3_render.py examples/docx/samples/invoice.docx
wrote examples/docx/samples/invoice_rendered.docx
$ uv run --with python-docx python examples/docx/step1_extract_text.py examples/docx/samples/invoice_rendered.docx
Invoice INV-0042
Design	$1,200.00
Development	$3,400.00
PAID
```

The `{%tr %}` rows became one real table row per line item, the tag-only rows are gone, and the
`PAID` paragraph survived because `paid` was true — set it to `False` and the paragraph disappears.
`samples/` is generated output and is not committed.

docxtpl goes further than this example — `InlineImage` drops a picture in from the context,
`tpl.new_subdoc()` embeds a whole generated document, and `{{ var | safe }}` inserts raw XML. The
[docxtpl] docs cover them; the workflow stays the same: author, extract, check, render.

[docxtpl]: https://docxtpl.readthedocs.io
[python-docx]: https://python-docx.readthedocs.io
[RichText]: https://docxtpl.readthedocs.io/en/latest/#richtext
