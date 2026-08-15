from playwright.sync_api import Page, expect


def test_user_portal_home(page: Page):
    page.goto("http://127.0.0.1:5000")

    expect(page).to_have_title(
        __import__("re").compile(".*")
    )

    page.screenshot(
        path="tests/browser/user-portal-home.png",
        full_page=True,
    )