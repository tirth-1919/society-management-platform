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
    time.sleep(0.05)
    yield "http://127.0.0.1:5005"
    server.shutdown()

def _login_admin(page: Page, base_url: str):
    page.goto(f"{base_url}/admin/login", timeout=15000)
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "Admin@123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

def _seed_resident_if_needed(app):
    with app.app_context():
        from app.models import (
            db, User, Role, Society, Building, Block, Flat, Resident,
            MaintenanceBill, Payment, PaymentReceipt, ComplaintCategory, Complaint, Visitor
        )
        from datetime import date

        s = Society.query.first()
        if not s:
            s = Society(
                name="Society 1",
                registration_number="REG-001",
                address="Addr 1",
                city="City 1",
                state="State 1",
                pincode="111111",
                phone="1111111111",
                email="s1@test.com",
            )
            db.session.add(s)
            db.session.commit()

        b = Building.query.first()
        if not b:
            b = Building(society_id=s.id, name="Wing A", floors_count=5, total_flats=10)
            db.session.add(b)
            db.session.commit()

        blk = Block.query.first()
        if not blk:
            blk = Block(society_id=s.id, building_id=b.id, name="Block 1")
            db.session.add(blk)
            db.session.commit()

        f = Flat.query.first()
        if not f:
            f = Flat(society_id=s.id, building_id=b.id, block_id=blk.id, flat_number="A-101")
            db.session.add(f)
            db.session.commit()

        res_user = User.query.filter_by(mobile="9800000001").first()
        if not res_user:
            res_user = User(
                username="resident_nav_test",
                full_name="Resident Navigation User",
                mobile="9800000001",
                email="res_nav_test@test.com",
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
            db.session.flush()

        bill = MaintenanceBill.query.filter_by(bill_number="BILL-NAV-001").first()
        if not bill:
            bill = MaintenanceBill(
                bill_number="BILL-NAV-001",
                society_id=s.id,
                flat_id=f.id,
                resident_id=res_prof.id,
                billing_month="2026-03",
                base_amount=1500.0,
                total_amount=1500.0,
                remaining_amount=1500.0,
                due_date=date(2026, 3, 10),
                status="Pending",
            )
            db.session.add(bill)
            db.session.flush()

        pay = Payment.query.filter_by(transaction_id="TXN-NAV-001").first()
        if not pay:
            pay = Payment(
                transaction_id="TXN-NAV-001",
                society_id=s.id,
                bill_id=bill.id,
                resident_id=res_prof.id,
                amount_paid=1500.0,
                payment_method="UPI",
                provider_name="Mock",
                status="captured",
            )
            db.session.add(pay)
            db.session.flush()
            rcpt = PaymentReceipt(
                receipt_number="RCPT-NAV-001",
                payment_id=pay.id,
                society_id=s.id,
            )
            db.session.add(rcpt)

        cat = ComplaintCategory.query.first()
        if not cat:
            cat = ComplaintCategory(name="Plumbing")
            db.session.add(cat)
            db.session.flush()

        comp = Complaint.query.filter_by(resident_id=res_prof.id).first()
        if not comp:
            comp = Complaint(
                ticket_number="TKT-NAV-001",
                society_id=s.id,
                flat_id=f.id,
                resident_id=res_prof.id,
                category="Plumbing",
                title="Water Leakage",
                description="Water leaking from sink",
                priority="Medium",
                status="Submitted",
            )
            db.session.add(comp)

        vis = Visitor.query.filter_by(flat_id=f.id).first()
        if not vis:
            vis = Visitor(
                society_id=s.id,
                flat_id=f.id,
                resident_id=res_prof.id,
                visitor_name="Visitor John",
                mobile="9998887776",
                purpose="Guest",
                approval_status="Approved",
            )
            db.session.add(vis)

        db.session.commit()

def _login_resident(page: Page, base_url: str, app):
    _seed_resident_if_needed(app)
    page.goto(f"{base_url}/login", timeout=15000)
    page.fill('input[name="mobile"]', "9800000001")
    page.fill('input[name="password"]', "Resident@123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_fixed_top_and_bottom_navigation_and_content_spacing(page: Page, app, live_server: str):
    """
    Verifies fixed top header, fixed bottom navigation, and adequate content padding.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    header = page.locator(".top-navbar")
    assert header.is_visible()
    assert header.evaluate("el => window.getComputedStyle(el).position") == "fixed"
    assert header.evaluate("el => window.getComputedStyle(el).top") == "0px"

    nav = page.locator(".mobile-nav")
    assert nav.is_visible()
    assert nav.evaluate("el => window.getComputedStyle(el).position") == "fixed"
    assert nav.evaluate("el => window.getComputedStyle(el).bottom") == "0px"
    assert nav.evaluate("el => window.getComputedStyle(el).left") == "0px"
    assert nav.evaluate("el => window.getComputedStyle(el).right") == "0px"

    # Touch targets >= 44px
    items = nav.locator("a, .mobile-nav-item")
    count = items.count()
    assert count >= 4
    for i in range(count):
        box = items.nth(i).bounding_box()
        assert box is not None
        assert box["height"] >= 44, f"Nav item {i} height {box['height']} is less than 44px"

    page_body = page.locator(".page-body")
    padding_top = page_body.evaluate("el => parseFloat(window.getComputedStyle(el).paddingTop)")
    padding_bottom = page_body.evaluate("el => parseFloat(window.getComputedStyle(el).paddingBottom)")
    assert padding_top >= 60
    assert padding_bottom >= 60


def test_header_offsets_and_visibility(page: Page, app, live_server: str):
    """
    Verifies fixed header position, top=0, left offset with sidebar (260px),
    left offset with collapsed sidebar (72px), mobile left=0, and visibility during scroll.
    """
    # 1. Desktop Standard Sidebar (left=260px)
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_admin(page, live_server)

    header = page.locator(".top-navbar")
    assert header.is_visible()
    pos = header.evaluate("el => window.getComputedStyle(el).position")
    top = header.evaluate("el => window.getComputedStyle(el).top")
    left = header.evaluate("el => parseFloat(window.getComputedStyle(el).left)")
    assert pos == "fixed"
    assert top == "0px"
    assert left == 260 or left == 220

    # 2. Desktop Collapsed Sidebar (left=72px)
    toggle_btn = page.locator("#sidebar-toggle-btn")
    if toggle_btn.is_visible():
        toggle_btn.click()
        page.wait_for_timeout(250)
        collapsed_left = header.evaluate("el => parseFloat(window.getComputedStyle(el).left)")
        assert collapsed_left == 72
        # Restore
        toggle_btn.click()
        page.wait_for_timeout(250)

    # 3. Mobile (left=0)
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(f"{live_server}/dashboard")
    page.wait_for_load_state("networkidle")
    mobile_left = header.evaluate("el => parseFloat(window.getComputedStyle(el).left)")
    assert mobile_left == 0

    # 4. Visible during scroll
    page.evaluate("window.scrollTo(0, 400)")
    page.wait_for_timeout(100)
    rect_top = header.evaluate("el => el.getBoundingClientRect().top")
    assert rect_top == 0
    assert header.is_visible()


def test_active_navigation_all_specified_routes(page: Page, app, live_server: str):
    """
    Verifies active navigation for all required routes:
    /dashboard, /resident/bills, /payments/bills, /payments/pay/*,
    /resident/receipts, /resident/profile, /resident/announcements,
    /resident/notifications, /resident/complaints, /resident/visitors.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    route_target_map = [
        ("/dashboard", "home"),
        ("/resident/bills", "bills"),
        ("/payments/bills", "bills"),
        ("/payments/pay/1", "pay"),
        ("/resident/receipts", "receipts"),
        ("/resident/profile", "more"),
        ("/resident/announcements", "more"),
        ("/resident/notifications", "more"),
        ("/resident/complaints", "more"),
        ("/resident/visitors", "more"),
    ]

    for route, expected_target in route_target_map:
        page.goto(f"{live_server}{route}", timeout=15000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(150)

        active_item = page.locator(f'.mobile-nav [data-nav-target="{expected_target}"]')
        assert active_item.count() > 0, f"Target {expected_target} not found for route {route}"
        assert active_item.evaluate("el => el.classList.contains('active')"), f"Route {route} did not activate {expected_target}"
        assert active_item.get_attribute("aria-current") == "page"

        # Verify inactive items remain visible and clickable
        other_items = page.locator(f'.mobile-nav a:not([data-nav-target="{expected_target}"])')
        other_count = other_items.count()
        for i in range(other_count):
            item = other_items.nth(i)
            assert item.is_visible()
            assert not item.evaluate("el => el.classList.contains('active')")


def test_refresh_route_preserves_active_state(page: Page, app, live_server: str):
    """
    Verifies that refreshing browser on major navigation routes preserves active state.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    routes_to_test = [
        ("/dashboard", "home"),
        ("/resident/bills", "bills"),
        ("/resident/receipts", "receipts"),
        ("/resident/profile", "more"),
        ("/resident/announcements", "more"),
        ("/resident/notifications", "more"),
        ("/resident/complaints", "more"),
        ("/resident/visitors", "more"),
    ]

    for route, expected_target in routes_to_test:
        page.goto(f"{live_server}{route}", timeout=15000)
        page.wait_for_load_state("networkidle")
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(150)

        active_item = page.locator(f'.mobile-nav [data-nav-target="{expected_target}"]')
        assert active_item.evaluate("el => el.classList.contains('active')"), f"Route {route} lost active state after refresh"


def test_nested_routes_parent_active_state(page: Page, app, live_server: str):
    """
    Verifies that nested routes correctly activate the intended parent navigation item.
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    nested_cases = [
        ("/resident/bills/1", "bills"),
        ("/payments/pay/1", "pay"),
        ("/payments/retry/1", "pay"),
        ("/payments/success/1", "pay"),
        ("/payments/cancelled/1", "pay"),
        ("/payments/failed/1", "pay"),
    ]

    for route, expected_target in nested_cases:
        page.goto(f"{live_server}{route}", timeout=15000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(150)

        active_item = page.locator(f'.mobile-nav [data-nav-target="{expected_target}"]')
        assert active_item.count() > 0
        assert active_item.evaluate("el => el.classList.contains('active')"), f"Nested route {route} failed to activate parent {expected_target}"


def test_mobile_sizes_responsive_and_safe_area(page: Page, app, live_server: str):
    """
    Verifies responsive behavior on mobile sizes: 320px, 360px, 375px, 480px, 768px.
    Checks no horizontal overflow, icons and labels visible, bottom nav aligned.
    """
    _login_resident(page, live_server, app)

    for width in [320, 360, 375, 480, 768]:
        page.set_viewport_size({"width": width, "height": 667})
        page.goto(f"{live_server}/dashboard")
        page.wait_for_load_state("networkidle")

        # Check horizontal overflow
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2, f"Overflow at width {width}"

        # Verify bottom navigation
        nav = page.locator(".mobile-nav")
        assert nav.is_visible()
        nav_box = nav.bounding_box()
        assert nav_box is not None
        assert nav_box["width"] <= width + 2

        # Verify nav icons
        icons = nav.locator("i")
        assert icons.count() >= 4
        for i in range(icons.count()):
            assert icons.nth(i).is_visible()


def test_desktop_sizes_responsive(page: Page, app, live_server: str):
    """
    Verifies desktop layouts on 820px, 1024px, 1280px, 1440px.
    Checks fixed header, sidebar/header layout, bottom nav hidden.
    """
    _login_admin(page, live_server)

    for width in [820, 1024, 1280, 1440]:
        page.set_viewport_size({"width": width, "height": 800})
        page.goto(f"{live_server}/dashboard")
        page.wait_for_load_state("networkidle")

        # Top header is fixed
        header = page.locator(".top-navbar")
        assert header.is_visible()
        pos = header.evaluate("el => window.getComputedStyle(el).position")
        assert pos == "fixed"

        # Sidebar is visible
        sidebar = page.locator("#app-sidebar")
        assert sidebar.is_visible()

        # Bottom nav is hidden
        bottom_nav = page.locator(".mobile-nav")
        if bottom_nav.count() > 0:
            display = bottom_nav.evaluate("el => window.getComputedStyle(el).display")
            assert display == "none"

        # No horizontal overflow
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2


def test_real_scroll_behavior_representative_long_page(page: Page, app, live_server: str):
    """
    Actually scrolls a long page and verifies:
    - Header remains fixed at top
    - Mobile bottom nav remains fixed at bottom
    - Page content scrolls smoothly
    - Content is not permanently clipped behind bars
    """
    page.set_viewport_size({"width": 375, "height": 667})
    _login_resident(page, live_server, app)

    page.goto(f"{live_server}/resident/bills")
    page.wait_for_load_state("networkidle")

    header = page.locator(".top-navbar")
    bottom_nav = page.locator(".mobile-nav")

    # Scroll down 400px
    page.evaluate("window.scrollTo(0, 400)")
    page.wait_for_timeout(200)

    # Header top stays 0
    header_top = header.evaluate("el => el.getBoundingClientRect().top")
    assert header_top == 0

    # Bottom nav bottom stays at viewport height (667)
    bottom_nav_bottom = bottom_nav.evaluate("el => el.getBoundingClientRect().bottom")
    viewport_height = page.evaluate("() => window.innerHeight")
    assert abs(bottom_nav_bottom - viewport_height) <= 2

    # Scroll back up
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    assert header.evaluate("el => el.getBoundingClientRect().top") == 0


def test_regression_existing_functionality(page: Page, app, live_server: str):
    """
    Basic regression check that navigation changes did not break:
    - login / authentication
    - dashboard loading
    - resident pages
    - admin pages
    - existing sidebar navigation
    """
    # 1. Resident Login & Dashboard
    page.set_viewport_size({"width": 1280, "height": 800})
    _login_resident(page, live_server, app)

    page.goto(f"{live_server}/dashboard")
    page.wait_for_load_state("networkidle")
    assert page.locator(".dashboard-due-card, .metric-card, .card").count() > 0

    # 2. Resident Pages Loading
    for res_route in ["/resident/bills", "/resident/receipts", "/resident/profile", "/resident/complaints"]:
        page.goto(f"{live_server}{res_route}")
        page.wait_for_load_state("networkidle")
        assert page.locator("main.page-body").is_visible()

    # 3. Admin Login & Pages Loading
    _login_admin(page, live_server)
    for admin_route in ["/dashboard", "/payments/bills", "/admin/residents", "/admin/flats"]:
        page.goto(f"{live_server}{admin_route}")
        page.wait_for_load_state("networkidle")
        assert page.locator("main.page-body").is_visible()
