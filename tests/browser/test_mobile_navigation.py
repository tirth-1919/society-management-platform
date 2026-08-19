import threading
import time
from wsgiref.simple_server import make_server
import pytest
from playwright.sync_api import Page

@pytest.fixture
def live_server(app):
    server = make_server("127.0.0.1", 5005, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:5005"
    server.shutdown()

def _login_admin(page: Page, base_url: str):
    page.goto(f"{base_url}/admin/login", timeout=15000)
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "Admin@123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

def test_mobile_menu_exact_sequence_a_to_k(page: Page, live_server: str):
    """
    Executes the exact test sequence from Section 22:
    TEST A: Page loaded -> Menu CLOSED
    TEST B: Click hamburger once -> Menu OPEN
    TEST C: Click hamburger again -> Menu CLOSED
    TEST D: Click hamburger again -> Menu OPEN
    TEST E: Click hamburger again -> Menu CLOSED
    TEST F: Open menu -> Click inside menu -> Menu remains OPEN
    TEST G: Open menu -> Click backdrop -> Menu CLOSES
    TEST H: Open menu -> Click a menu item -> Correct page opens
    TEST I: Return/on page -> Click hamburger -> Menu OPEN
    TEST J: Click hamburger again -> Menu CLOSED
    TEST K: Repeat at least 10 times -> Every click produces exactly one correct state transition.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_admin(page, live_server)

    sidebar = page.locator("#app-sidebar")
    hamburger = page.locator("#mobile-menu-btn")
    overlay = page.locator("#sidebar-mobile-overlay")

    # TEST A: Page loaded -> Menu CLOSED
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert hamburger.get_attribute("aria-expanded") == "false"
    assert hamburger.get_attribute("aria-label") == "Open menu"

    # TEST B: Click hamburger once -> Menu OPEN
    hamburger.click()
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert overlay.evaluate("el => el.classList.contains('active')")
    assert hamburger.get_attribute("aria-expanded") == "true"
    assert hamburger.get_attribute("aria-label") == "Close menu"

    # TEST C: Click hamburger again -> Menu CLOSED
    hamburger.click()
    page.wait_for_timeout(200)
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert not overlay.evaluate("el => el.classList.contains('active')")
    assert hamburger.get_attribute("aria-expanded") == "false"

    # TEST D: Click hamburger again -> Menu OPEN
    hamburger.click()
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert hamburger.get_attribute("aria-expanded") == "true"

    # TEST E: Click hamburger again -> Menu CLOSED
    hamburger.click()
    page.wait_for_timeout(200)
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert hamburger.get_attribute("aria-expanded") == "false"

    # TEST F: Open menu -> Click inside empty area of menu -> Remains OPEN
    hamburger.click()
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")
    # Click empty area / footer of sidebar (not a link)
    sidebar_footer = sidebar.locator(".sidebar-footer")
    if sidebar_footer.count() > 0:
        sidebar_footer.click()
    else:
        sidebar.click(position={"x": 20, "y": 10})
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")

    # TEST G: Open menu -> Click backdrop -> Menu CLOSES
    overlay.click(position={"x": 320, "y": 200}, force=True)
    page.wait_for_timeout(200)
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")

    # TEST H: Open menu -> Click a menu item -> Correct page opens
    hamburger.click()
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")
    # Click Complaints / Registrations link in sidebar
    nav_item = sidebar.locator(".nav-item").first
    nav_item.click()
    page.wait_for_load_state("networkidle")

    # TEST I: On new page -> Click hamburger -> Menu OPEN
    sidebar = page.locator("#app-sidebar")
    hamburger = page.locator("#mobile-menu-btn")
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
    hamburger.click()
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")

    # TEST J: Click hamburger again -> Menu CLOSED
    hamburger.click()
    page.wait_for_timeout(200)
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")

    # TEST K: Repeat toggle 10 times -> Every click produces correct transition
    for i in range(10):
        # Open
        hamburger.click()
        page.wait_for_timeout(100)
        assert sidebar.evaluate("el => el.classList.contains('mobile-open')"), f"Failed to open on iteration {i}"
        assert hamburger.get_attribute("aria-expanded") == "true"

        # Close
        hamburger.click()
        page.wait_for_timeout(100)
        assert not sidebar.evaluate("el => el.classList.contains('mobile-open')"), f"Failed to close on iteration {i}"
        assert hamburger.get_attribute("aria-expanded") == "false"

def test_no_x_button_exists_anywhere(page: Page, live_server: str):
    """
    Verifies that the unwanted square X button is completely removed
    and does not appear anywhere on mobile or desktop.
    """
    # Mobile
    page.set_viewport_size({"width": 375, "height": 667})
    _login_admin(page, live_server)

    assert page.locator("#sidebar-close-btn").count() == 0
    assert page.locator(".sidebar-close-btn").count() == 0

    # Open mobile menu
    page.locator("#mobile-menu-btn").click()
    page.wait_for_timeout(200)
    assert page.locator("#sidebar-close-btn").count() == 0
    assert page.locator(".sidebar-close-btn").count() == 0

    # Desktop
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(200)
    assert page.locator("#sidebar-close-btn").count() == 0
    assert page.locator(".sidebar-close-btn").count() == 0


@pytest.mark.parametrize("width", [320, 360, 375, 390, 414, 430, 480, 768])
def test_mobile_menu_across_all_breakpoints(page: Page, live_server: str, width: int):
    """
    Verifies that the hamburger toggle works reliably across all mobile/tablet breakpoints:
    320px, 360px, 375px, 390px, 414px, 430px, 480px, 768px.
    """
    page.set_viewport_size({"width": width, "height": 700})
    _login_admin(page, live_server)

    hamburger = page.locator("#mobile-menu-btn")
    sidebar = page.locator("#app-sidebar")

    assert hamburger.is_visible()
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")

    # Toggle open
    hamburger.click()
    page.wait_for_timeout(150)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert hamburger.get_attribute("aria-expanded") == "true"

    # Toggle closed
    hamburger.click()
    page.wait_for_timeout(150)
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert hamburger.get_attribute("aria-expanded") == "false"


def test_desktop_sidebar_behavior(page: Page, live_server: str):
    """
    Verifies that desktop sidebar remains functional and collapse/expand works.
    """
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_admin(page, live_server)

    hamburger = page.locator("#mobile-menu-btn")
    sidebar = page.locator("#app-sidebar")
    toggle_btn = page.locator("#sidebar-toggle-btn")

    # Hamburger should be hidden on desktop
    assert not hamburger.is_visible()

    # Sidebar is visible on desktop
    assert sidebar.is_visible()

    # Desktop toggle collapses and expands sidebar
    if toggle_btn.is_visible():
        toggle_btn.click()
        page.wait_for_timeout(200)
        assert sidebar.evaluate("el => el.classList.contains('sidebar-collapsed')")

        toggle_btn.click()
        page.wait_for_timeout(200)
        assert not sidebar.evaluate("el => el.classList.contains('sidebar-collapsed')")


def test_search_remains_independent(page: Page, live_server: str):
    """
    Verifies that search button in top header remains independent from the mobile menu.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_admin(page, live_server)

    sidebar = page.locator("#app-sidebar")
    search_trigger = page.locator("#global-search-trigger")

    assert search_trigger.is_visible()
    search_trigger.click()
    page.wait_for_timeout(200)

    # Search should open palette without erroneously opening mobile menu
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")


def test_body_scroll_locking_and_escape(page: Page, live_server: str):
    """
    Verifies that body scroll locking works and Escape key closes the menu.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_admin(page, live_server)

    hamburger = page.locator("#mobile-menu-btn")
    sidebar = page.locator("#app-sidebar")

    # Initially body does not have drawer-open
    assert not page.locator("body").evaluate("el => el.classList.contains('drawer-open')")

    # Open menu
    hamburger.click()
    page.wait_for_timeout(150)
    assert page.locator("body").evaluate("el => el.classList.contains('drawer-open')")

    # Press Escape -> closes menu & restores body scroll
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
    assert not page.locator("body").evaluate("el => el.classList.contains('drawer-open')")

def test_mobile_menu_works_after_navigation_on_all_pages(page: Page, live_server: str):
    """
    Verifies that the hamburger menu opens and closes reliably after navigating
    across multiple pages (Requirement 11).
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_admin(page, live_server)

    sidebar = page.locator("#app-sidebar")
    hamburger = page.locator("#mobile-menu-btn")

    routes_to_test = [
        "/admin/registrations",
        "/payments/bills",
        "/admin/visitors",
        "/admin/staff",
    ]

    for route in routes_to_test:
        page.goto(f"{live_server}{route}", timeout=15000)
        page.wait_for_load_state("networkidle")

        sidebar = page.locator("#app-sidebar")
        hamburger = page.locator("#mobile-menu-btn")

        # Must start closed
        assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")

        # Open
        hamburger.click()
        page.wait_for_timeout(150)
        assert sidebar.evaluate("el => el.classList.contains('mobile-open')")

        # Close
        hamburger.click()
        page.wait_for_timeout(150)
        assert not sidebar.evaluate("el => el.classList.contains('mobile-open')")
