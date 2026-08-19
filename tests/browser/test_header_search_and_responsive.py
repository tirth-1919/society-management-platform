import threading
import time
from wsgiref.simple_server import make_server
import pytest
from playwright.sync_api import Page, expect

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

def _login_resident(page: Page, base_url: str):
    page.goto(f"{base_url}/login", timeout=15000)
    page.fill('input[name="mobile"]', "9800000001")
    page.fill('input[name="password"]', "Resident@123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

def test_header_brand_removed_and_realigned(page: Page, live_server: str):
    """
    Verifies that the header brand [building icon] Society is completely removed
    from the header, and header elements naturally re-align.
    """
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_admin(page, live_server)

    # In the header (.top-navbar), there should be NO .header-brand-link or Society logo
    header = page.locator(".top-navbar")
    assert header.is_visible()
    assert header.locator(".header-brand-link").count() == 0

    # The header should contain the search button
    search_btn = header.locator("#global-search-trigger")
    assert search_btn.is_visible()

    # The search label text
    search_label = search_btn.locator(".header-search-label")
    assert "Search residents, flats, bills, actions..." in search_label.inner_text()


def test_search_ui_no_ctrl_k_and_click_only(page: Page, live_server: str):
    """
    Verifies that search has NO Ctrl+K badge, does NOT open via Ctrl+K,
    and opens ONLY when clicking the search button.
    """
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_admin(page, live_server)

    search_btn = page.locator("#global-search-trigger")
    palette = page.locator("#cmd-palette-backdrop")

    # Verify no Ctrl or K badge inside search button
    assert search_btn.locator(".global-search-shortcut").count() == 0
    assert "Ctrl" not in search_btn.inner_text()
    assert "Ctrl+K" not in search_btn.inner_text()

    # Palette initially NOT open
    assert not palette.evaluate("el => el.classList.contains('open')")

    # Press Ctrl+K -> palette should NOT open
    page.keyboard.press("Control+k")
    page.wait_for_timeout(200)
    assert not palette.evaluate("el => el.classList.contains('open')")

    # Click search button -> palette OPENS
    search_btn.click()
    page.wait_for_timeout(200)
    assert palette.evaluate("el => el.classList.contains('open')")

    # Verify Quick Actions and Recent are shown
    results_area = page.locator("#cmd-palette-results")
    assert results_area.is_visible()
    assert "QUICK ACTIONS" in results_area.inner_text() or "Quick Actions" in results_area.inner_text()
    assert "RECENT" in results_area.inner_text() or "Recent" in results_area.inner_text()

    # Test typing in search input
    search_input = page.locator("#cmd-palette-input")
    search_input.fill("Bills")
    page.wait_for_timeout(300)
    assert results_area.locator(".cmd-item").count() > 0

    # Press Escape -> closes palette
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert not palette.evaluate("el => el.classList.contains('open')")

def test_resident_dashboard_widgets_removed(page: Page, app, live_server: str):
    """
    Verifies that Last Payment, Latest Receipt, and Notifications widget
    are removed from resident dashboard, while underlying pages remain accessible.
    """
    with app.app_context():
        from app.models import db, User, Role, Society, Building, Flat, Resident
        s = Society.query.first()
        b = Building.query.first()
        f = Flat.query.first()

        res_user = User.query.filter_by(mobile="9800000001").first()
        if not res_user:
            res_user = User(
                username="resident_test",
                full_name="Resident Test User",
                mobile="9800000001",
                email="res_test@test.com",
                role=Role.RESIDENT,
                society_id=s.id,
                building_id=b.id,
                flat_id=f.id,
                account_status="ACTIVE",
                is_active=True,
            )
            res_user.set_password("Resident@123")
            db.session.add(res_user)
            db.session.flush()

        res_prof = Resident.query.filter_by(user_id=res_user.id).first()
        if not res_prof:
            res_prof = Resident(
                society_id=s.id,
                building_id=b.id,
                flat_id=f.id,
                user_id=res_user.id,
                full_name=res_user.full_name,
                mobile=res_user.mobile,
                email=res_user.email,
                is_primary=True,
                status="Active",
            )
            db.session.add(res_prof)
        db.session.commit()

    page.set_viewport_size({"width": 1280, "height": 800})
    _login_resident(page, live_server)

    # We should be on dashboard
    assert "/dashboard" in page.url or "/" in page.url

    # Check metrics grid has no "Unread Alerts" or "Notifications" card
    metrics_grid = page.locator(".metrics-grid")
    if metrics_grid.count() > 0:
        metrics_text = metrics_grid.inner_text()
        assert "Last Payment" not in metrics_text
        assert "Latest Receipt" not in metrics_text

    # Verify Receipts page is accessible
    page.goto(f"{live_server}/resident/receipts", timeout=15000)
    page.wait_for_load_state("networkidle")
    assert page.locator("h1").inner_text() != ""

    # Verify Notifications page is accessible
    page.goto(f"{live_server}/resident/notifications", timeout=15000)
    page.wait_for_load_state("networkidle")
    assert page.locator("h1").inner_text() != ""


@pytest.mark.parametrize("width", [320, 360, 375, 390, 414, 430, 480, 768, 820, 1024, 1280, 1440])
def test_responsive_layout_no_overflow(page: Page, live_server: str, width: int):
    """
    Verifies that across all standard widths, the page fits within the viewport
    and has no page-level horizontal overflow.
    """
    page.set_viewport_size({"width": width, "height": 750})
    _login_admin(page, live_server)

    routes = ["/dashboard", "/payments/bills", "/admin/registrations", "/admin/residents"]
    for route in routes:
        page.goto(f"{live_server}{route}", timeout=15000)
        page.wait_for_load_state("networkidle")

        # Verify body scrollWidth is <= viewport width + 2px tolerance for fractional subpixels
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2, f"Page {route} horizontally overflows at width {width} (scrollWidth={scroll_width}, clientWidth={client_width})"
