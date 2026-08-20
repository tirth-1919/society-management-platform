'''Read-only smoke coverage for every static GET route registered by Flask.

Run with: python -m pytest tests/test_route_smoke.py -v -s
'''

from __future__ import annotations
import traceback
from dataclasses import dataclass
from flask import Flask
from werkzeug.routing import Rule
@dataclass
class RouteResult:
    rule: Rule
    status: int
    exception: BaseException | None = None
    traceback_text: str = ""


def _safe_get_rules(app: Flask) -> list[Rule]:
    '''Return unique, static rules that advertise GET without invoking them.'''
    rules = []
    seen = set()
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if "GET" not in rule.methods or rule.arguments:
            continue
        key = (rule.rule, rule.endpoint)
        if key not in seen:
            seen.add(key)
            rules.append(rule)
    return rules

def _result_for_rule(app: Flask, client, rule: Rule) -> RouteResult:
    '''Issue exactly one GET and retain propagated test-environment exceptions.'''
    try:
        response = client.get(rule.rule, follow_redirects=False)
        return RouteResult(rule=rule, status=response.status_code)
    except Exception as exc:  # noqa: BLE001 - the smoke test must collect every failure
        return RouteResult(
            rule=rule,
            status=500,
            exception=exc,
            traceback_text=traceback.format_exc(),
        )


def _label(status: int) -> str:
    if status == 500:
        return "RED"
    if 200 <= status < 300:
        return "PASS"
    if 300 <= status < 400:
        return "REDIRECT"
    if 400 <= status < 500:
        return "CLIENT"
    return "UNEXPECTED"


def _print_500(result: RouteResult) -> None:
    print("\n" + "=" * 50)
    print("500 ERROR")
    print("=" * 50)
    print(f"Endpoint: {result.rule.endpoint}")
    print(f"URL: {result.rule}")
    print(f"Status: {result.status}")
    if result.exception is not None:
        print("\nException:")
        print(f"{type(result.exception).__name__}: {result.exception}")
        print("\nTraceback:")
        print(result.traceback_text.rstrip())
    else:
        print("\nException: Not exposed by Flask (the route returned a 500 response).")
    print("=" * 50)


def test_registered_get_routes_have_no_server_errors(app, client):
    '''Exercise only static GET endpoints; fail once after reporting all 500s.'''
    results = [_result_for_rule(app, client, rule) for rule in _safe_get_rules(app)]

    print("\n=== ROUTE SMOKE TEST ===\n")
    for result in results:
        print(f"{_label(result.status):10} {str(result.rule):<40} {result.status}")

    server_errors = [result for result in results if result.status == 500]
    summary = {
        "passed": sum(200 <= result.status < 300 for result in results),
        "redirects": sum(300 <= result.status < 400 for result in results),
        "client_errors": sum(400 <= result.status < 500 for result in results),
        "unexpected": sum(
            result.status < 200 or (500 < result.status < 600)
            for result in results
        ),
    }
    print("\n=== SUMMARY ===\n")
    print(f"Total routes tested: {len(results)}")
    print(f"Passed: {summary['passed']}")
    print(f"Redirects: {summary['redirects']}")
    print(f"Client errors: {summary['client_errors']}")
    print(f"SERVER ERRORS (500): {len(server_errors)}")
    print(f"Other unexpected statuses: {summary['unexpected']}")

    if server_errors:
        print("\n500 ROUTES:")
        for result in server_errors:
            print(f"- {result.rule} ({result.rule.endpoint})")
        for result in server_errors:
            _print_500(result)

    assert not server_errors, f"{len(server_errors)} routes returned HTTP 500"
