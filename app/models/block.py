# Block model is defined in tenant.py alongside Building and Flat
# to ensure correct SQLAlchemy relationship resolution order.
# This file re-exports it for convenience.
from app.models.tenant import Block

__all__ = ["Block"]
