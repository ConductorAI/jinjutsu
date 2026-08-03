import json
import sys

from jinjutsu import analyze_jinja_template, extract_docx_text

report = analyze_jinja_template(extract_docx_text(sys.argv[1]))
for diagnostic in report.diagnostics:
    print(diagnostic)
print(json.dumps(report.schema, indent=2))
