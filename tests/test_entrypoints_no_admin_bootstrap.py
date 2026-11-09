import runpy

from flask import Flask
from app.models import Society, User


def test_entrypoints_start_without_creating_demo_data_or_admin(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("USER_PORT", "0")
    monkeypatch.setenv("ADMIN_PORT", "0")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "entrypoint-test-session")
    monkeypatch.setattr(Flask, "run", lambda self, *args, **kwargs: None)

    user_entry = runpy.run_path("run_user.py", run_name="__main__")
    admin_entry = runpy.run_path("run_admin.py", run_name="__main__")

    for entry in (user_entry, admin_entry):
        app = entry["app"]
        with app.app_context():
            assert User.query.filter_by(username="admin").count() == 0
            assert Society.query.count() == 0

        client = app.test_client()
        assert client.get("/login").status_code == 200
        assert client.get("/admin/login").status_code == 200
