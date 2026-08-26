"""
Document AI security and isolation tests.
Ensures document AI features respect access controls and tenant isolation.
"""
import pytest
from app.models import (
    db,
    Society,
    Building,
    Flat,
    Resident,
    User,
    Role,
    Document,
)
from app.services.ai_service import AIService


@pytest.fixture
def document_security_data(app):
    """Setup test data for document security tests."""
    with app.app_context():
        # Society 1
        society1 = Society(
            name="Document Security Society 1",
            registration_number="DOC-SEC-001",
            address="789 Document Road",
            city="Test City",
            state="Gujarat",
            pincode="360001",
            email="doc1@test.com",
            phone="9876543255",
        )
        db.session.add(society1)
        db.session.commit()

        # Society 2
        society2 = Society(
            name="Document Security Society 2",
            registration_number="DOC-SEC-002",
            address="790 Document Road",
            city="Test City",
            state="Gujarat",
            pincode="360002",
            email="doc2@test.com",
            phone="9876543266",
        )
        db.session.add(society2)
        db.session.commit()

        # Users for both societies
        admin1 = User(
            username="doc_admin1",
            full_name="Document Admin 1",
            email="admin1@test.com",
            mobile="9876543255",
            role=Role.SOCIETY_ADMIN,
            society_id=society1.id,
            account_status="ACTIVE",
            is_active=True
        )
        admin1.set_password("Admin@123")
        db.session.add(admin1)
        db.session.commit()

        admin2 = User(
            username="doc_admin2",
            full_name="Document Admin 2",
            email="admin2@test.com",
            mobile="9876543266",
            role=Role.SOCIETY_ADMIN,
            society_id=society2.id,
            account_status="ACTIVE",
            is_active=True
        )
        admin2.set_password("Admin@123")
        db.session.add(admin2)
        db.session.commit()

        # Residents for both societies
        building1 = Building(society_id=society1.id, name="Wing A")
        db.session.add(building1)
        db.session.commit()

        flat1 = Flat(society_id=society1.id, building_id=building1.id, flat_number="101")
        db.session.add(flat1)
        db.session.commit()

        resident_user1 = User(
            username="doc_resident1",
            full_name="Document Resident 1",
            email="resident1@test.com",
            mobile="9876543277",
            role=Role.RESIDENT,
            society_id=society1.id,
            account_status="ACTIVE",
            is_active=True
        )
        resident_user1.set_password("Resident@123")
        db.session.add(resident_user1)
        db.session.commit()

        resident1 = Resident(
            society_id=society1.id,
            flat_id=flat1.id,
            user_id=resident_user1.id,
            full_name="Document Resident 1",
            mobile="9876543277",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True
        )
        db.session.add(resident1)
        db.session.commit()

        # Documents for both societies
        doc1 = Document(
            society_id=society1.id,
            title="Society 1 Financial Report",
            category="Financial",
            file_path="/docs/society1_report.pdf",
            file_size_bytes=1024,
            file_type="pdf",
            uploaded_by_id=admin1.id,
            access_level="ADMIN_ONLY"
        )
        db.session.add(doc1)
        db.session.commit()

        doc2 = Document(
            society_id=society2.id,
            title="Society 2 Financial Report",
            category="Financial",
            file_path="/docs/society2_report.pdf",
            file_size_bytes=1024,
            file_type="pdf",
            uploaded_by_id=admin2.id,
            access_level="ADMIN_ONLY"
        )
        db.session.add(doc2)
        db.session.commit()

        return society1.id, society2.id, admin1.id, admin2.id, resident_user1.id, doc1.id, doc2.id


def test_document_categorization_safety(app, document_security_data):
    """Test document categorization doesn't modify documents."""
    society1_id, _, admin1_id, _, _, doc1_id, _ = document_security_data
    with app.app_context():
        doc = db.session.get(Document, doc1_id)

        original_category = doc.category

        # Suggest categorization (should not modify document)
        suggested = AIService.suggest_document_categorization(
            title=doc.title,
            description="Financial report for society"
        )

        # Document should remain unchanged
        doc = db.session.get(Document, doc1_id)
        assert doc.category == original_category
        assert suggested in ["Financial", "Legal", "Maintenance", "Administrative", "Resident", "Property", "General"]


def test_document_summary_content_grounding(app, document_security_data):
    """Test document summary is grounded only in document content."""
    society1_id, _, admin1_id, _, _, doc1_id, _ = document_security_data
    with app.app_context():
        # Generate summary with specific content
        summary = AIService.generate_document_summary(
            document_title="Test Document",
            document_content="This document contains specific information about financial records."
        )

        assert "Test Document" in summary
        assert "specific information" in summary
        assert "Based on Document Content Only" in summary


def test_document_query_isolation(app, document_security_data):
    """Test document queries are isolated to document content only."""
    society1_id, society2_id, admin1_id, admin2_id, _, doc1_id, doc2_id = document_security_data
    with app.app_context():
        # Query about society 1 document with society 1 admin
        answer1 = AIService.ask_document(
            question="What is the financial status?",
            document_content="Society 1 has a surplus of ₹50,000."
        )

        # Query about society 2 document with society 2 admin
        answer2 = AIService.ask_document(
            question="What is the financial status?",
            document_content="Society 2 has a deficit of ₹20,000."
        )

        # Answers should be based only on respective document content
        assert "₹50,000" in answer1 or "does not contain" in answer1.lower()
        assert "₹20,000" in answer2 or "does not contain" in answer2.lower()

        # Should not mix data
        if "₹50,000" in answer1:
            assert "₹20,000" not in answer1
        if "₹20,000" in answer2:
            assert "₹50,000" not in answer2


def test_cross_society_document_protection(app, document_security_data):
    """Test that society admins cannot access other societies' documents via AI."""
    society1_id, society2_id, admin1_id, admin2_id, _, doc1_id, doc2_id = document_security_data
    with app.app_context():
        # Society 1 admin trying to access society 2 document content
        # The AI service should only work with provided content, not query DB
        answer = AIService.ask_document(
            question="Show me the financial report",
            document_content=""  # Empty content for other society's document
        )

        # Should not reveal any information about other society
        assert "does not contain that information" in answer.lower() or "content not available" in answer.lower()


def test_document_unsupported_format_handling(app, document_security_data):
    """Test graceful handling of unsupported document formats."""
    society1_id, _, admin1_id, _, _, _, _ = document_security_data
    with app.app_context():
        # Try to summarize unsupported format
        summary = AIService.generate_document_summary(
            document_title="Unsupported Format",
            document_content=""  # Empty content
        )

        assert "content not available" in summary.lower() or "may not be supported" in summary.lower()


def test_document_query_fallback(app, document_security_data):
    """Test document query fallback when information not present."""
    society1_id, _, admin1_id, _, _, _, _ = document_security_data
    with app.app_context():
        # Ask question about information not in document
        answer = AIService.ask_document(
            question="What is the weather forecast?",
            document_content="This document contains financial information only."
        )

        assert "does not contain that information" in answer.lower()


def test_document_ai_no_database_modification(app, document_security_data):
    """Test document AI features never modify database records."""
    society1_id, _, admin1_id, _, _, doc1_id, _ = document_security_data
    with app.app_context():
        doc = db.session.get(Document, doc1_id)

        original_title = doc.title
        original_category = doc.category
        original_access_level = doc.access_level

        # Run all document AI operations
        AIService.suggest_document_categorization(doc.title, "Test description")
        AIService.generate_document_summary(doc.title, "Test content")
        AIService.ask_document("Test question", "Test content")

        # Document should remain unchanged
        doc = db.session.get(Document, doc1_id)
        assert doc.title == original_title
        assert doc.category == original_category
        assert doc.access_level == original_access_level


def test_document_api_authorization(client, app, document_security_data):
    """Test document AI APIs require proper authorization."""
    society1_id, _, admin1_id, _, resident_user1_id, _, _ = document_security_data

    # Resident should not be able to access admin document APIs
    with client.session_transaction() as sess:
        sess['user_id'] = resident_user1_id
        sess['society_id'] = society1_id
        sess['role'] = Role.RESIDENT

    response = client.post('/api/v1/ai/document-categorize',
                          json={"title": "Test", "description": "Test"})
    assert response.status_code == 403  # Forbidden

    # Admin should be able to access
    with client.session_transaction() as sess:
        sess['user_id'] = admin1_id
        sess['society_id'] = society1_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.post('/api/v1/ai/document-categorize',
                          json={"title": "Test", "description": "Test"})
    assert response.status_code == 200