'''Safe, read-only audit of registered Flask routes and source assets.

This audit sends GET requests only and uses the isolated pytest application.
'''
from __future__ import annotations
import re
from pathlib import Path
from collections import Counter
from flask import Flask
_DYNAMIC = re.compile(r"<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>")

def _rules(app: Flask):
    return sorted((rule for rule in app.url_map.iter_rules() if "GET" in rule.methods), key=lambda r: (r.rule, r.endpoint))

def _safe_url(rule):
    return _DYNAMIC.sub(lambda m: "999" if m.group("converter") in (None, "int") else "audit-nonexistent", rule.rule)

def test_complete_safe_get_error_audit(app, client):
    results = []
    for rule in _rules(app):
        response = client.get(_safe_url(rule), follow_redirects=False)
        results.append(response.status_code)
        print(f"{rule.endpoint:50} {_safe_url(rule):65} {response.status_code}")
    counts = Counter(results)
    print("\n=== COMPLETE ERROR AUDIT ===")
    for status in (200, 301, 302, 303, 307, 308, 400, 401, 403, 404, 405, 500):
        print(f"{status}: {counts[status]}")
    print(f"OTHER: {sum(count for status, count in counts.items() if status not in (200,301,302,303,307,308,400,401,403,404,405,500))}")
    assert counts[500] == 0, f"Safe GET audit observed {counts[500]} HTTP 500 responses"

def test_source_assets_exist_and_templates_compile(app):
    template_root = Path(app.root_path) / "templates"
    templates = list(template_root.rglob("*.html"))
    assert templates
    for template in templates:
        app.jinja_env.get_template(template.relative_to(template_root).as_posix())
    static_root = Path(app.static_folder)
    assert static_root.exists()
    assert list(static_root.rglob("*"))

def test_registered_get_routes_have_unique_endpoint_url_pairs(app):
    pairs = [(rule.endpoint, rule.rule) for rule in _rules(app)]
    assert len(pairs) == len(set(pairs))
