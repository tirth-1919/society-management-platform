<<<<<<< HEAD
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
=======
from playwright.sync_api import Page, expect


def test_user_portal_home(page: Page):
    page.goto("http://127.0.0.1:5000")
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    expect(page).to_have_title(
        __import__("re").compile(".*")
    )

    page.screenshot(
        path="tests/browser/user-portal-home.png",
        full_page=True,
    )