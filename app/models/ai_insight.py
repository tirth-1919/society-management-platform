from app.models.tenant import db
from app.utils import utcnow
import json


class AIInsight(db.Model):
    __tablename__ = "ai_insights"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=True, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )

    category = db.Column(
        db.String(50), nullable=False, index=True
    )  # FINANCE, MAINTENANCE, SECURITY, UTILITY, ENGAGEMENT
    insight_type = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    confidence_score = db.Column(db.Float, default=1.0)
    explanation = db.Column(db.Text, nullable=True)
    payload_json = db.Column(db.Text, nullable=True)

    is_dismissed = db.Column(db.Boolean, default=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    resident = db.relationship("Resident", foreign_keys=[resident_id], lazy=True)
    user = db.relationship("User", foreign_keys=[user_id], lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_payload(self):
        try:
            return json.loads(self.payload_json or "{}")
        except Exception:
            return {}


class AIPrediction(db.Model):
    __tablename__ = "ai_predictions"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    target_entity_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # BILL, COMPLAINT, ASSET, INVENTORY, VISITOR, UTILITY
    target_entity_id = db.Column(db.Integer, nullable=True, index=True)
    prediction_type = db.Column(db.String(80), nullable=False, index=True)
    predicted_value = db.Column(db.String(255), nullable=False)
    confidence = db.Column(db.Float, default=1.0)
    features_json = db.Column(db.Text, nullable=True)
    model_version = db.Column(db.String(50), default="v1.0.0-deterministic")
    created_at = db.Column(db.DateTime, default=utcnow)
    valid_until = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class AIFeedback(db.Model):
    __tablename__ = "ai_feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    insight_id = db.Column(
        db.Integer, db.ForeignKey("ai_insights.id"), nullable=True, index=True
    )
    prediction_id = db.Column(
        db.Integer, db.ForeignKey("ai_predictions.id"), nullable=True, index=True
    )
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5, or 1/-1 for thumbs up/down
    feedback_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", foreign_keys=[user_id], lazy=True)
    insight = db.relationship("AIInsight", foreign_keys=[insight_id], lazy=True)
    prediction = db.relationship("AIPrediction", foreign_keys=[prediction_id], lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
