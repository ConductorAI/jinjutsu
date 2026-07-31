# CLI examples

`invoice.jinja` parses cleanly. `client.jinja` has a problem. All commands run from the repo root.

## No flags — warnings and tree

```sh
$ jinjutsu examples/cli/invoice.jinja
invoice             object
|-- number          string
|-- lines           list of objects
|   |-- desc        string
|   `-- amount      string
`-- paid            boolean
```

```sh
$ jinjutsu examples/cli/client.jinja
===== warnings =================================================
Line 1: Field 'items' collides with a built-in method
  Found: {{ client.items }}
  Fix:   {{ client['items'] }}
  Reason: Jinja reads '.items' as the value's own method, so the document renders the method instead of your value. Use bracket syntax.
  {{ client.items }}

===== tree =====================================================
client              object
`-- items           string
```

## `--warnings`

```sh
$ jinjutsu examples/cli/client.jinja --warnings
Line 1: Field 'items' collides with a built-in method
  Found: {{ client.items }}
  Fix:   {{ client['items'] }}
  Reason: Jinja reads '.items' as the value's own method, so the document renders the method instead of your value. Use bracket syntax.
  {{ client.items }}
```

## `--tree`

```sh
$ jinjutsu examples/cli/client.jinja --tree
client              object
`-- items           string
```

## `--schema`

```sh
$ jinjutsu examples/cli/client.jinja --schema
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "client": {
      "type": "object",
      "properties": {
        "items": {
          "type": "string"
        }
      }
    }
  }
}
```

## `--all`

All three sections in the order above, each behind its divider. The flags also compose, so
`--warnings --schema` gives those two and no tree.

## Several files

```sh
$ jinjutsu examples/cli/*.jinja --warnings
== examples/cli/client.jinja
Line 1: Field 'items' collides with a built-in method
  Found: {{ client.items }}
  Fix:   {{ client['items'] }}
  Reason: Jinja reads '.items' as the value's own method, so the document renders the method instead of your value. Use bracket syntax.
  {{ client.items }}

== examples/cli/invoice.jinja
Nothing wrong
```

## Template text instead of a file

```sh
$ jinjutsu "hi {{ variable + 1 }}"
variable            string
```

Quote it — an unquoted `{{ ... }}` is brace expansion in bash and zsh.

## Exit codes

`0` clean, `1` at least one diagnostic, `2` an argument that is neither a readable file nor a template.
