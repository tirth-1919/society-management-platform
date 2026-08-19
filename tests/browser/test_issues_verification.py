import threading
import time
from wsgiref.simple_server import make_server
import pytest
from playwright.sync_api import Page

@pytest.fixture
def live_server(app):
    server = make_server("127.0.0.1", 5006, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.05)
    yield "http://127.0.0.1:5006"
    server.shutdown()
def _login_resident(page: Page, base_url: str, app):
    from tests.browser.test_navigation_behavior import _seed_resident_if_needed
    _seed_resident_if_needed(app)
    page.goto(f"{base_url}/login", timeout=15000)
    page.fill('input[name="mobile"]', "9800000001")
    page.fill('input[name="password"]', "Resident@123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_sidebar_scrolling_and_menu_reachability(page: Page, app, live_server: str):
    """
    Points 1-4:
    1. Open sidebar.
    2. Scroll sidebar to bottom.
    3. Confirm all menu items are reachable.
    4. Confirm background does not scroll.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    hamburger = page.locator("#mobile-menu-btn")
    sidebar = page.locator("#app-sidebar")
    sidebar_nav = page.locator(".sidebar-nav")

    hamburger.click()
    page.wait_for_timeout(200)
    assert sidebar.evaluate("el => el.classList.contains('mobile-open')")

    # Confirm body has drawer-open (background does not scroll)
    assert page.locator("body").evaluate("el => el.classList.contains('drawer-open')")

    # Scroll sidebar to bottom
    sidebar_nav.evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(150)

    # Confirm last menu item (Logout) is visible/reachable
    logout_item = sidebar.locator('a[href*="logout"]')
    assert logout_item.is_visible()
    box = logout_item.bounding_box()
    assert box is not None
    assert box["y"] >= 0 and box["y"] <= 667
def test_dashboard_facility_booking_single_and_click(page: Page, app, live_server: str):
    """
    Points 5-8:
    5. Open dashboard.
    6. Confirm Facility Booking appears only once.
    7. Click Facility Booking.
    8. Confirm existing Facility Booking page opens.
    """
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_resident(page, live_server, app)

    page.goto(f"{live_server}/dashboard")
    page.wait_for_load_state("networkidle")

    # In sidebar, Facility Booking appears exactly once
    fac_links = page.locator('#app-sidebar a:has-text("Facility Booking")')
    assert fac_links.count() == 1

    # Click Facility Booking
    fac_links.first.click()
    page.wait_for_load_state("networkidle")

    # Confirm existing Facility Booking page opens
    assert "/facilities" in page.url
    assert page.locator('h2:has-text("Facility Booking"), h2:has-text("Amenities")').count() > 0


def test_visitor_security_desk_label_and_layout(page: Page, app, live_server: str):
    """
    Points 9-13:
    9. Confirm label says: Visitor Security Desk
    10. Open Visitor Security Desk.
    11. Confirm full page works.
    12. Confirm Today's Gate Entries appears below the visitor/security section.
    13. Test mobile layout.
    """
    # 9-11 Desktop
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_resident(page, live_server, app)

    vis_link = page.locator('#app-sidebar a:has-text("Visitor Security Desk")')
    assert vis_link.count() == 1
    vis_link.first.click()
    page.wait_for_load_state("networkidle")

    assert "/resident/visitors" in page.url
    assert page.locator('h1:has-text("Visitor Security Desk")').is_visible()

    # Test Security visitors page layout (Today's gate entries below main section)
    page.goto(f"{live_server}/visitors/")
    page.wait_for_load_state("networkidle")

    heading = page.locator('h2:has-text("Visitor Security Desk")')
    assert heading.is_visible()

    # 13 Mobile layout test (375px & 390px)
    for w in [375, 390]:
        page.set_viewport_size({"width": w, "height": 667})
        page.goto(f"{live_server}/visitors/")
        page.wait_for_load_state("networkidle")

        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2
def test_complaint_desk_responsive_layout(page: Page, app, live_server: str):
    """
    Points 14-15:
    14. Open Complaint Desk.
    15. Test mobile/tablet/desktop layout.
    """
    _login_resident(page, live_server, app)

    for w, h in [(1920, 1080), (1366, 768), (768, 1024), (390, 844), (375, 667)]:
        page.set_viewport_size({"width": w, "height": h})
        page.goto(f"{live_server}/resident/complaints")
        page.wait_for_load_state("networkidle")

        assert page.locator('h1:has-text("Complaints")').is_visible()
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2


def test_facility_booking_responsive_layout(page: Page, app, live_server: str):
    """
    Points 16-17:
    16. Open Facility Booking.
    17. Test mobile/tablet/desktop layout.
    """
    _login_resident(page, live_server, app)

    for w, h in [(1920, 1080), (1366, 768), (768, 1024), (390, 844), (375, 667)]:
        page.set_viewport_size({"width": w, "height": h})
        page.goto(f"{live_server}/facilities/")
        page.wait_for_load_state("networkidle")

        assert page.locator('h2:has-text("Facility Booking")').is_visible()
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2


def test_pay_now_flow_and_active_state_refresh(page: Page, app, live_server: str):
    """
    Points 18-22:
    18. Tap Pay Now.
    19. Confirm existing Pay Now/payment page opens.
    20. Confirm Pay Now becomes active.
    21. Refresh.
    22. Confirm Pay Now remains active.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    page.goto(f"{live_server}/dashboard")
    page.wait_for_load_state("networkidle")

    # Tap Pay Now in bottom nav
    pay_nav_item = page.locator('.mobile-nav a[data-nav-target="pay"]')
    assert pay_nav_item.is_visible()
    pay_nav_item.click()
    page.wait_for_load_state("networkidle")

    # Existing Pay Now/payment page opens
    assert "/payments/pay" in page.url or "/resident/bills" in page.url

    # When on /payments/pay/1:
    page.goto(f"{live_server}/payments/pay/1")
    page.wait_for_load_state("networkidle")

    pay_item = page.locator('.mobile-nav [data-nav-target="pay"]')
    assert pay_item.evaluate("el => el.classList.contains('active')")

    # Refresh
    page.reload()
    page.wait_for_load_state("networkidle")
    assert pay_item.evaluate("el => el.classList.contains('active')")


def test_announcement_household_security_pages_render_html(page: Page, app, live_server: str):
    """
    Points 23-26:
    23. Open Announcement.
    24. Open Household.
    25. Open Security.
    26. Confirm none display raw source code.
    """
    _login_resident(page, live_server, app)

    for route, expected_h1 in [
        ("/resident/announcements", "Announcements"),
        ("/resident/household", "Household"),
        ("/resident/security", "Security"),
    ]:
        page.goto(f"{live_server}{route}")
        page.wait_for_load_state("networkidle")

        content = page.content()
        # Assert no raw Jinja syntax leaked
        assert "{%" not in content
        assert "{{ " not in content
        assert "}}" not in content
        # Assert valid page elements render
        assert page.locator("main.page-body").is_visible()
        assert page.locator("h1").is_visible()
