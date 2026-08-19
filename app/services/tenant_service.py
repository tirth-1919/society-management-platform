from flask import session, abort
from app.models import Role


class TenantService:
    @staticmethod
    def get_current_society_id():
        """Extracts society_id from user session."""
        return session.get("society_id")

    @staticmethod
    def enforce_tenant_isolation(user, requested_society_id):
        """
        Enforces tenant isolation rule:
        Super Admin can access any society.
        Society users can ONLY access their assigned society.
        If unauthorized cross-tenant attempt occurs, abort with 403 Forbidden.
        """
        if not user:
            abort(401, description="Authentication required")

        if user.role == Role.SUPER_ADMIN:
            return True

        if user.society_id != requested_society_id:
            abort(403, description="Forbidden: Cross-tenant access is not authorized")

        return True

    @staticmethod
    def filter_query_by_society(query, model_class, society_id):
        """Filters SQLAlchemy query by society_id if the model has a society_id field."""
        if hasattr(model_class, "society_id") and society_id:
            return query.filter(model_class.society_id == society_id)
        return query

    @staticmethod
    def ensure_default_blocks_and_flats(society_id):
        """
        Ensures the six blocks (Block A, Block B, Block C, Block D, Block E, Block F)
        and all 44 floor-based flats per block (Floors 1-11, 4 flats per floor:
        101-104, 201-204, ..., 1101-1104) exist for the given society.
        Total = 6 blocks * 44 flats = 264 flats.
        """
        if not society_id:
            return

        from app.models import db, Building, Block, Flat

        block_letters = ["A", "B", "C", "D", "E", "F"]

        # Build floor flats list: Floors 1 to 11, flats 1 to 4 per floor
        floor_flats = []
        for fl in range(1, 12):
            for unit in range(1, 5):
                flat_no = f"{fl}0{unit}"
                floor_flats.append((fl, flat_no))

        changed = False
        for letter in block_letters:
            block_name = f"Block {letter}"

            building = Building.query.filter_by(
                society_id=society_id, name=block_name
            ).first()
            if not building:
                building = Building(
                    society_id=society_id,
                    name=block_name,
                    floors_count=11,
                    total_flats=44,
                )
                db.session.add(building)
                db.session.flush()
                changed = True
            else:
                if building.floors_count != 11 or building.total_flats != 44:
                    building.floors_count = 11
                    building.total_flats = 44
                    changed = True

            block = Block.query.filter_by(
                society_id=society_id, building_id=building.id, name=block_name
            ).first()
            if not block:
                block = Block(
                    society_id=society_id,
                    building_id=building.id,
                    name=block_name,
                    floors_count=11,
                )
                db.session.add(block)
                db.session.flush()
                changed = True
            else:
                if block.floors_count != 11:
                    block.floors_count = 11
                    changed = True

            existing_flats = {
                f.flat_number: f
                for f in Flat.query.filter_by(
                    society_id=society_id, building_id=building.id
                ).all()
            }

            for floor_num, flat_num in floor_flats:
                if flat_num not in existing_flats:
                    flat = Flat(
                        society_id=society_id,
                        building_id=building.id,
                        block_id=block.id,
                        flat_number=flat_num,
                        floor_number=floor_num,
                        area_sqft=1000.0 + (floor_num * 10),
                        flat_type="2BHK" if floor_num <= 6 else "3BHK",
                        occupancy_status="Available",
                    )
                    db.session.add(flat)
                    changed = True
                else:
                    f = existing_flats[flat_num]
                    if f.block_id != block.id or f.floor_number != floor_num:
                        f.block_id = block.id
                        f.floor_number = floor_num
                        changed = True

        if changed:
            db.session.commit()
