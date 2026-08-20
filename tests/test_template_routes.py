"Template and endpoint integrity checks for the Flask application."""
from __future__ import annotations
import re
from pathlib import Path

def test_all_application_templates_are_discoverable(app):
    template_root = Path(app.root_path) / "templates"
    templates = sorted(path.relative_to(template_root).as_posix() for path in template_root.rglob("*.html"))
    assert templates
    for template in templates:
        app.jinja_env.get_template(template)
        print(f"template PASS {template}")

def test_static_endpoint_references_resolve(app):
    template_root = Path(app.root_path) / "templates"
    known = set(app.view_functions)
    refs = set()
    pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
    for path in template_root.rglob("*.html"):
        refs.update(pattern.findall(path.read_text(encoding="utf-8")))
    missing = sorted(ref for ref in refs if ref not in known and not ref.startswith("static"))
    assert not missing, "Missing url_for endpoints: " + ", ".join(missing)

def test_registered_unauthenticated_get_templates_do_not_500(app, client):
    failures = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if "GET" not in rule.methods or rule.arguments:
            continue
        response = client.get(rule.rule, follow_redirects=False)
        print(f"route {rule.endpoint:45} {rule.rule:50} {response.status_code}")
        if response.status_code == 500:
            failures.append((rule.rule, rule.endpoint))
    assert not failures, f"Template route HTTP 500s: {failures}"
