import threading
import time
from wsgiref.simple_server import make_server
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def live_server(app):
    server = make_server("127.0.0.1", 5000, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:5000"
    server.shutdown()


def test_user_portal_home(page: Page, live_server):
    page.goto(live_server, timeout=10000)

    expect(page).to_have_title(
        __import__("re").compile(".*")
    )

    page.screenshot(
        path="tests/browser/user-portal-home.png",
        full_page=True,
    )