import pytest
from app import create_app
from app.models import db, User, Role, Society, Building, Flat


@pytest.fixture
def app():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        db.create_all()

        # Seed test societies
        s1 = Society(
            name="Society 1",
            registration_number="REG-001",
            address="Addr 1",
            city="City 1",
            state="State 1",
            pincode="111111",
            phone="1111111111",
            email="s1@test.com",
        )
        s2 = Society(
            name="Society 2",
            registration_number="REG-002",
            address="Addr 2",
            city="City 2",
            state="State 2",
            pincode="222222",
            phone="2222222222",
            email="s2@test.com",
        )
        db.session.add_all([s1, s2])
        db.session.commit()

        # Seed buildings (Wings)
        b1 = Building(society_id=s1.id, name="Wing A", floors_count=5, total_flats=10)
        b2 = Building(society_id=s2.id, name="Wing X", floors_count=5, total_flats=10)
        db.session.add_all([b1, b2])
        db.session.commit()

        # Seed blocks
        from app.models import Block

        blk1 = Block(society_id=s1.id, building_id=b1.id, name="Block 1")
        blk2 = Block(society_id=s2.id, building_id=b2.id, name="Block X")
        db.session.add_all([blk1, blk2])
        db.session.commit()

        # Seed flats
        f1 = Flat(
            society_id=s1.id, building_id=b1.id, block_id=blk1.id, flat_number="A-101"
        )
        f2 = Flat(
            society_id=s2.id, building_id=b2.id, block_id=blk2.id, flat_number="X-101"
        )
        db.session.add_all([f1, f2])
        db.session.commit()

        # Seed Super Admin
        admin = User(
            username="admin",
            full_name="Super Admin",
            mobile="9000000000",
            email="admin@test.com",
            role=Role.SUPER_ADMIN,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()

        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
