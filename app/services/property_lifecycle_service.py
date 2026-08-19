import re
from app.models import (
    db,
    Flat,
    Resident,
    PropertyOccupancyHistory,
    AuditLog,
)
from app.utils import utcnow


class PropertyLifecycleService:
    @staticmethod
    def normalize_property_key(block_or_building_name, flat_number):
        """
        Normalizes any block/flat variation into a canonical string key: <BLOCK>-<FLAT>.
        Examples:
          'B', '202'       -> 'B-202'
          'b', ' 202 '     -> 'B-202'
          'Wing B', '202'  -> 'WING B-202'
          'B-202', None    -> 'B-202'
          'b - 202', None  -> 'B-202'
          'B 202', None    -> 'B-202'
        """
        if flat_number is None and block_or_building_name:
            raw = str(block_or_building_name).strip().upper()
            # Normalize internal spacing around hyphens or spaces: 'B - 202', 'B 202' -> 'B-202'
            parts = re.split(r"[\s\-]+", raw)
            if len(parts) == 2 and parts[0] and parts[1]:
                return f"{parts[0]}-{parts[1]}"
            return raw

        b = str(block_or_building_name or "").strip().upper()
        f = str(flat_number or "").strip().upper()
        # Strip any extraneous hyphens
        b = b.strip("- ")
        f = f.strip("- ")
        if b and f:
            return f"{b}-{f}"
        return f or b or "UNKNOWN"

    @staticmethod
    def parse_block_flat_input(input_str):
        """
        Parses user input like 'B-202', 'b 202', 'Block A - 101' into (prefix, flat_number).
        """
        if not input_str:
            return "", ""
        cleaned = str(input_str).strip().upper()
        match = re.search(r"^(.*?)[-\s]+([0-9A-Z]+)$", cleaned)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return cleaned, ""

    @staticmethod
    def find_flat_by_canonical_key(society_id, canonical_key):
        """
        Looks up a flat within a society matching the normalized canonical key.
        """
        if not society_id or not canonical_key:
            return None
        norm_target = PropertyLifecycleService.normalize_property_key(canonical_key, None)
        flats = Flat.query.filter_by(society_id=society_id).all()
        for flat in flats:
            if PropertyLifecycleService.normalize_property_key(
                flat.block.name if flat.block else (flat.building.name if flat.building else ""),
                flat.flat_number
            ) == norm_target:
                return flat
        return None

    @staticmethod
    def record_move_in(
        society_id,
        flat_id,
        resident_id,
        user_id=None,
        resident_type="Owner",
        move_in_date=None,
        admin_user=None,
    ):
        """
        Activates a resident for a flat and initializes a dedicated occupancy history record.
        Ensures a completely fresh financial state for the new resident without mixing prior occupant records.
        """
        flat = db.session.get(Flat, flat_id)
        resident = db.session.get(Resident, resident_id)
        if not flat or flat.society_id != society_id:
            raise ValueError(f"Flat #{flat_id} not found in society #{society_id}")
        if not resident or resident.society_id != society_id:
            raise ValueError(f"Resident #{resident_id} not found in society #{society_id}")

        # Update resident occupancy
        resident.flat_id = flat.id
        resident.occupancy_status = "Active"
        resident.is_primary = True
        resident.move_in_date = move_in_date or utcnow().date()
        if hasattr(resident, "move_out_date"):
            resident.move_out_date = None

        # Update flat status
        flat.occupancy_status = "Occupied"

        # Create independent occupancy history record
        occupancy = PropertyOccupancyHistory(
            society_id=society_id,
            flat_id=flat.id,
            resident_id=resident.id,
            user_id=user_id or resident.user_id,
            resident_type=resident_type or resident.resident_type,
            occupancy_status="Active",
            move_in_date=resident.move_in_date,
            approved_by_id=admin_user.id if admin_user else None,
        )
        db.session.add(occupancy)

        # Audit event
        audit = AuditLog(
            user_id=admin_user.id if admin_user else user_id,
            action="RESIDENT_MOVE_IN",
            details=f"Resident {resident.full_name} moved into {flat.property_key} on {resident.move_in_date}",
        )
        db.session.add(audit)
        db.session.commit()
        return occupancy

    @staticmethod
    def record_move_out(
        resident_id,
        move_out_date=None,
        reason="Move out requested",
        admin_user=None,
    ):
        """
        Deactivates resident's active occupancy, archives the occupancy history,
        and marks the flat as Available/Vacant. Preserves all past bills, payments, and receipts.
        """
        resident = db.session.get(Resident, resident_id)
        if not resident:
            raise ValueError(f"Resident #{resident_id} not found")

        flat = resident.flat
        m_date = move_out_date or utcnow().date()

        # Update resident record
        resident.occupancy_status = "Moved Out"
        resident.is_primary = False
        if hasattr(resident, "move_out_date"):
            resident.move_out_date = m_date
        if hasattr(resident, "move_out_reason"):
            resident.move_out_reason = reason
        if hasattr(resident, "moved_out_approved_by") and admin_user:
            resident.moved_out_approved_by = admin_user.id

        # Update active occupancy history records
        active_histories = PropertyOccupancyHistory.query.filter_by(
            resident_id=resident.id,
            flat_id=resident.flat_id,
            occupancy_status="Active",
        ).all()
        for h in active_histories:
            h.occupancy_status = "Moved Out"
            h.move_out_date = m_date
            h.move_out_reason = reason

        # Check if flat still has other active residents; if not, mark flat Available/Vacant
        other_actives = (
            Resident.query.filter_by(flat_id=resident.flat_id, occupancy_status="Active")
            .filter(Resident.id != resident.id)
            .count()
        )
        if flat and other_actives == 0:
            flat.occupancy_status = "Vacant"

        audit = AuditLog(
            user_id=admin_user.id if admin_user else resident.user_id,
            action="RESIDENT_MOVE_OUT",
            details=f"Resident {resident.full_name} moved out of flat #{resident.flat_id} on {m_date}. Reason: {reason}",
        )
        db.session.add(audit)
        db.session.commit()
        return {
            "success": True,
            "resident_id": resident.id,
            "move_out_date": m_date.isoformat() if hasattr(m_date, "isoformat") else str(m_date),
            "flat_status": flat.occupancy_status if flat else "Vacant",
        }

    @staticmethod
    def get_property_occupancy_history(flat_id):
        """
        Retrieves the complete, chronological occupancy history of a property.
        """
        return (
            PropertyOccupancyHistory.query.filter_by(flat_id=flat_id)
            .order_by(PropertyOccupancyHistory.move_in_date.desc(), PropertyOccupancyHistory.created_at.desc())
            .all()
        )
