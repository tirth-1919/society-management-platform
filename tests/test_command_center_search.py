from app.models import db, User, Society, Resident, Flat, Role
from app.services.search_service import SearchService

def test_command_search_service_categories_and_limits(app):
    with app.app_context():
        society = Society.query.first()
        admin_user = User.query.filter_by(role=Role.SUPER_ADMIN).first()

        res = SearchService.global_search(admin_user, society.id, "Wing", category="category_flats", limit=3)
        assert res is not None
        assert "categories" in res
        assert res["query"] == "Wing"

def test_command_search_api_endpoint(client, app):
    with app.app_context():
        admin = User.query.filter_by(role=Role.SUPER_ADMIN).first()
        admin_id = admin.id
        society = Society.query.first()
        soc_id = society.id

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = soc_id
        sess['role'] = Role.SUPER_ADMIN

    response = client.get('/api/v1/search?q=Wing&limit=5')
    assert response.status_code == 200
    data = response.get_json()
    assert "categories" in data
    assert "query" in data
    assert data["query"] == "Wing"

def test_resident_cannot_access_unauthorized_records(client, app):
    with app.app_context():
        society = Society.query.first()
        soc_id = society.id
        flat = Flat.query.first()

        # Create a resident user
        res_user = User(
            full_name="Test Resident User",
            mobile="9888877771",
            email="res1@test.com",
            role=Role.RESIDENT,
            society_id=soc_id,
            account_status="ACTIVE",
            is_active=True
        )
        res_user.set_password("Pass@123")
        db.session.add(res_user)
        db.session.commit()

        resident = Resident(
            society_id=soc_id,
            user_id=res_user.id,
            flat_id=flat.id,
            full_name="Test Resident User",
            mobile="9888877771",
            resident_type="Owner"
        )
        db.session.add(resident)
        db.session.commit()

        res_user_id = res_user.id

    with client.session_transaction() as sess:
        sess['user_id'] = res_user_id
        sess['society_id'] = soc_id
        sess['role'] = Role.RESIDENT

    # Search for an admin entity or query
    response = client.get('/api/v1/search?q=Resident')
    assert response.status_code == 200
    data = response.get_json()
    assert "categories" in data
    cat_keys = [c.get("key") for c in data.get("categories", [])]
    assert "category_residents" not in cat_keys
