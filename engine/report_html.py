"""Optional HTML data embedding; no report UI or default template is shipped."""

import json
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).parent / "templates" / "report.html"
PLACEHOLDER = "<!--ORPHIC_REPORT_JSON-->"


def write_report_html(case_dir, template_path=None):
    """Embed report.json once, returning the written absolute path or None."""
    template = DEFAULT_TEMPLATE if template_path is None else Path(template_path)
    if template_path is None and not template.exists():
        return None
    case = Path(case_dir).resolve()
    source = template.read_text(encoding="utf-8")
    if source.count(PLACEHOLDER) != 1:
        raise ValueError("report template must contain exactly one " + PLACEHOLDER)
    content = (case / "report.json").read_text(encoding="utf-8")
    json.loads(content)  # Reject malformed data before touching report.html.
    # JSON has no \! escape: encode '<' to preserve comment openers losslessly.
    content = (content.replace("</", "<\\/").replace("<!--", "\\u003c!--")
               .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    script = '<script type="application/json" id="orphic-report">' + content + '</script>'
    output = case / "report.html"
    if output.is_symlink() or (output.exists() and (
            not output.is_file() or output.stat().st_nlink > 1)):
        raise ValueError("report HTML output must be a regular file without links")
    output.write_text(source.replace(PLACEHOLDER, script), encoding="utf-8", newline="\n")
    return output
