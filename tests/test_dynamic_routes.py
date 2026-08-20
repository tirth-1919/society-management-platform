"Safe dynamic-route audit: only GETs with non-existent identifiers."""
from __future__ import annotations
import re
from flask import Flask
_DYNAMIC = re.compile(r"<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>")

def _dynamic_get_rules(app: Flask):
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if "GET" in rule.methods and rule.arguments:
            yield rule

def _safe_path(rule):
    values = {name: "999" if converter in (None, "int") else "smoke-nonexistent" for converter, name in _DYNAMIC.findall(rule.rule)}
    return _DYNAMIC.sub(lambda match: values[match.group("name")], rule.rule)

def test_dynamic_get_routes_do_not_return_500(app, client):
    results = []
    for rule in _dynamic_get_rules(app):
        path = _safe_path(rule)
        response = client.get(path, follow_redirects=False)
        results.append((rule, path, response.status_code))
        print(f"{rule.endpoint:45} {path:60} {response.status_code}")
    errors = [(rule, path, status) for rule, path, status in results if status == 500]
    assert not errors, "Dynamic routes returned HTTP 500: " + ", ".join(f"{rule.rule} ({path})" for rule, path, _ in errors)

def test_dynamic_route_malformed_values_do_not_return_500(app, client):
    for rule in _dynamic_get_rules(app):
        if any(converter == "int" for converter, _ in _DYNAMIC.findall(rule.rule)):
            path = _DYNAMIC.sub(lambda match: "not-an-integer" if match.group("converter") == "int" else "smoke", rule.rule)
            response = client.get(path, follow_redirects=False)
            print(f"malformed {rule.endpoint:36} {path:60} {response.status_code}")
            assert response.status_code != 500, f"Malformed dynamic URL returned 500: {path}"
