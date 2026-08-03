import json
import sys

from step1_extract_text import extract_text

from jinjutsu import analyze_jinja_template

report = analyze_jinja_template(extract_text(sys.argv[1]))
for diagnostic in report.diagnostics:
    print(diagnostic)
print(json.dumps(report.schema, indent=2))
