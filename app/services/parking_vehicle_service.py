import re
from app.models import db, ParkingSlot, Vehicle, User, Resident, Flat, AuditLog
from app.services.notification_service import NotificationService
from app.utils import utcnow


class ParkingVehicleService:
    VALID_VEHICLE_TYPES = [
        "Car",
        "Bike",
        "Scooter",
        "Electric Car",
        "Electric Bike",
        "Cycle",
        "Commercial Vehicle",
        "Other",
    ]

    VALID_STATUSES = ["ACTIVE", "INACTIVE", "SOLD", "TRANSFERRED"]

    @staticmethod
    def normalize_plate(plate):
        """Removes spaces, hyphens, and converts to uppercase."""
        if not plate:
            return ""
        return re.sub(r"[\s\-_.\/]+", "", str(plate)).upper()

    @classmethod
    def register_vehicle(
        cls,
        society_id,
        owner_user_id,
        flat_id,
        vehicle_number,
        vehicle_type="Car",
        make=None,
        model=None,
        brand_model=None,
        color=None,
        resident_id=None,
        slot_id=None,
        parking_slot_number=None,
        secondary_mobile=None,
        email=None,
        notes=None,
        vehicle_photo=None,
        status="ACTIVE",
    ):
        """Registers a vehicle ensuring society-level active normalized plate uniqueness."""
        if not vehicle_number or not str(vehicle_number).strip():
            raise ValueError("Vehicle number plate is required.")

        normalized_plate = cls.normalize_plate(vehicle_number)
        if not normalized_plate:
            raise ValueError("Invalid vehicle number plate.")

        # Validate vehicle type
        if vehicle_type and vehicle_type not in cls.VALID_VEHICLE_TYPES:
            vehicle_type = "Car"

        # Check duplicate active vehicle within the same society
        existing = (
            Vehicle.query.filter_by(society_id=society_id)
            .filter(
                (Vehicle.normalized_number_plate == normalized_plate)
                | (Vehicle.vehicle_number == vehicle_number.strip())
            )
            .filter(Vehicle.status == "ACTIVE")
            .first()
        )
        if existing:
            raise ValueError("This vehicle number is already registered.")

        # Compute brand_model if make/model provided
        make_clean = (make or "").strip()
        model_clean = (model or "").strip()
        if not brand_model and (make_clean or model_clean):
            brand_model = f"{make_clean} {model_clean}".strip() or None

        # Resolve slot ID if parking slot number is provided
        if not slot_id and parking_slot_number:
            slot_obj = ParkingSlot.query.filter_by(
                society_id=society_id, slot_number=parking_slot_number.strip()
            ).first()
            if slot_obj:
                slot_id = slot_obj.id

        vehicle = Vehicle(
            society_id=society_id,
            owner_user_id=owner_user_id,
            resident_id=resident_id,
            flat_id=flat_id,
            vehicle_number=vehicle_number.strip().upper(),
            normalized_number_plate=normalized_plate,
            vehicle_type=vehicle_type,
            make=make_clean or None,
            model=model_clean or None,
            brand_model=brand_model or None,
            color=(color or "").strip() or None,
            parking_slot_id=slot_id,
            parking_slot_number=(parking_slot_number or "").strip() or None,
            secondary_mobile=(secondary_mobile or "").strip() or None,
            email=(email or "").strip() or None,
            notes=(notes or "").strip() or None,
            vehicle_photo=vehicle_photo,
            status=status if status in cls.VALID_STATUSES else "ACTIVE",
        )

        db.session.add(vehicle)
        db.session.flush()

        # Audit logging
        db.session.add(
            AuditLog(
                society_id=society_id,
                user_id=owner_user_id,
                action="VEHICLE_CREATED",
                details=f"Registered vehicle {vehicle.vehicle_number} ({vehicle.vehicle_type}) for Flat #{flat_id}",
            )
        )
        db.session.commit()
        return vehicle

    @classmethod
    def update_vehicle(
        cls,
        vehicle_id,
        user,
        make=None,
        model=None,
        color=None,
        vehicle_type=None,
        parking_slot_number=None,
        secondary_mobile=None,
        email=None,
        notes=None,
        vehicle_photo=None,
        number_plate=None,
        status=None,
    ):
        """Updates vehicle with strict ownership and society authorization checks."""
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError("Vehicle not found.")

        # Check authorization (owner or society admin/super admin)
        is_admin = user.role in ["Super Admin", "Society Admin"]
        is_owner = vehicle.owner_user_id == user.id or (
            vehicle.resident and vehicle.resident.user_id == user.id
        )

        if not is_admin and not is_owner:
            raise PermissionError("Unauthorized: You can only edit your own vehicles.")

        if not is_admin and vehicle.society_id != user.society_id:
            raise PermissionError("Unauthorized society access.")

        # Update plate if provided and changed
        if number_plate and number_plate.strip().upper() != vehicle.vehicle_number:
            new_norm = cls.normalize_plate(number_plate)
            # Duplicate check
            duplicate = (
                Vehicle.query.filter_by(society_id=vehicle.society_id)
                .filter(
                    (Vehicle.normalized_number_plate == new_norm)
                    | (Vehicle.vehicle_number == number_plate.strip().upper())
                )
                .filter(Vehicle.id != vehicle.id)
                .filter(Vehicle.status == "ACTIVE")
                .first()
            )
            if duplicate:
                raise ValueError("This vehicle number is already registered.")

            vehicle.vehicle_number = number_plate.strip().upper()
            vehicle.normalized_number_plate = new_norm

        if vehicle_type and vehicle_type in cls.VALID_VEHICLE_TYPES:
            vehicle_type_clean = vehicle_type
        else:
            vehicle_type_clean = vehicle.vehicle_type

        vehicle.vehicle_type = vehicle_type_clean
        if make is not None:
            vehicle.make = make.strip() or None
        if model is not None:
            vehicle.model = model.strip() or None
        if color is not None:
            vehicle.color = color.strip() or None

        vehicle.brand_model = f"{vehicle.make or ''} {vehicle.model or ''}".strip() or None

        if parking_slot_number is not None:
            vehicle.parking_slot_number = parking_slot_number.strip() or None
            # Sync slot ID if possible
            if vehicle.parking_slot_number:
                slot_obj = ParkingSlot.query.filter_by(
                    society_id=vehicle.society_id, slot_number=vehicle.parking_slot_number
                ).first()
                vehicle.parking_slot_id = slot_obj.id if slot_obj else None
            else:
                vehicle.parking_slot_id = None

        if secondary_mobile is not None:
            vehicle.secondary_mobile = secondary_mobile.strip() or None
        if email is not None:
            vehicle.email = email.strip() or None
        if notes is not None:
            vehicle.notes = notes.strip() or None
        if vehicle_photo is not None:
            vehicle.vehicle_photo = vehicle_photo

        if is_admin and status and status in cls.VALID_STATUSES:
            vehicle.status = status

        vehicle.updated_at = utcnow()

        db.session.add(
            AuditLog(
                society_id=vehicle.society_id,
                user_id=user.id,
                action="VEHICLE_UPDATED",
                details=f"Updated vehicle #{vehicle.id} ({vehicle.vehicle_number})",
            )
        )
        db.session.commit()
        return vehicle

    @classmethod
    def deactivate_vehicle(cls, vehicle_id, user, reason=None):
        """Soft deactivates a vehicle record."""
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError("Vehicle not found.")

        is_admin = user.role in ["Super Admin", "Society Admin"]
        is_owner = vehicle.owner_user_id == user.id or (
            vehicle.resident and vehicle.resident.user_id == user.id
        )

        if not is_admin and not is_owner:
            raise PermissionError("Unauthorized: You can only deactivate your own vehicles.")

        if not is_admin and vehicle.society_id != user.society_id:
            raise PermissionError("Unauthorized society access.")

        vehicle.status = "INACTIVE"
        vehicle.updated_at = utcnow()

        db.session.add(
            AuditLog(
                society_id=vehicle.society_id,
                user_id=user.id,
                action="VEHICLE_DEACTIVATED",
                details=f"Deactivated vehicle #{vehicle.id} ({vehicle.vehicle_number}){' - ' + reason if reason else ''}",
            )
        )
        db.session.commit()
        return vehicle

    @classmethod
    def reactivate_vehicle(cls, vehicle_id, user):
        """Reactivates an inactive vehicle (Admin action)."""
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError("Vehicle not found.")

        is_admin = user.role in ["Super Admin", "Society Admin"]
        if not is_admin:
            raise PermissionError("Unauthorized: Only admins can reactivate vehicles.")

        # Check if plate is already active elsewhere in society
        duplicate = (
            Vehicle.query.filter_by(society_id=vehicle.society_id)
            .filter(Vehicle.normalized_number_plate == vehicle.normalized_number_plate)
            .filter(Vehicle.id != vehicle.id)
            .filter(Vehicle.status == "ACTIVE")
            .first()
        )
        if duplicate:
            raise ValueError("Cannot reactivate: another vehicle with this number plate is already active.")

        vehicle.status = "ACTIVE"
        vehicle.updated_at = utcnow()

        db.session.add(
            AuditLog(
                society_id=vehicle.society_id,
                user_id=user.id,
                action="VEHICLE_REACTIVATED",
                details=f"Reactivated vehicle #{vehicle.id} ({vehicle.vehicle_number})",
            )
        )
        db.session.commit()
        return vehicle

    @classmethod
    def search_by_plate(cls, society_id, query_plate, active_only=True):
        """Alias for search_vehicles for backward compatibility."""
        return cls.search_vehicles(society_id, query_plate, active_only=active_only)

    @classmethod
    def search_vehicles(cls, society_id, query_text=None, vehicle_type=None, active_only=True):
        """Searches vehicles by plate (exact or partial), make, model, owner name, parking slot, or flat within a society.
        If query_text is empty or None, returns all visible active vehicles in the society."""
        from sqlalchemy import or_
        from app.models import Block, Building, ParkingSlot

        q = Vehicle.query.filter_by(society_id=society_id)
        if active_only:
            q = q.filter(Vehicle.status == "ACTIVE")

        # Apply vehicle type category filter if provided
        type_clean = (vehicle_type or "").strip().lower()
        if type_clean and type_clean not in ["all", ""]:
            if type_clean in ["car", "cars"]:
                q = q.filter(Vehicle.vehicle_type.in_(["Car", "Electric Car"]))
            elif type_clean in ["bike", "bikes", "scooter", "two-wheeler", "two wheeler"]:
                q = q.filter(Vehicle.vehicle_type.in_(["Bike", "Scooter", "Electric Bike", "Cycle"]))
            elif type_clean in ["other", "others"]:
                q = q.filter(Vehicle.vehicle_type.in_(["Commercial Vehicle", "Other"]))
            else:
                q = q.filter(Vehicle.vehicle_type.ilike(f"%{vehicle_type.strip()}%"))

        # If no search query, return all society vehicles
        if not query_text or not str(query_text).strip():
            return q.order_by(Vehicle.created_at.desc()).all()

        clean_q = str(query_text).strip()
        norm = cls.normalize_plate(clean_q)

        q = (
            q.outerjoin(Vehicle.flat)
            .outerjoin(Flat.block)
            .outerjoin(Flat.building)
            .outerjoin(Vehicle.owner)
            .outerjoin(Vehicle.resident)
            .outerjoin(Vehicle.parking_slot_rel)
        )

        conditions = [
            Vehicle.vehicle_number.ilike(f"%{clean_q}%"),
            Vehicle.vehicle_type.ilike(f"%{clean_q}%"),
            Vehicle.make.ilike(f"%{clean_q}%"),
            Vehicle.model.ilike(f"%{clean_q}%"),
            Vehicle.brand_model.ilike(f"%{clean_q}%"),
            Vehicle.color.ilike(f"%{clean_q}%"),
            Vehicle.parking_slot_number.ilike(f"%{clean_q}%"),
            ParkingSlot.slot_number.ilike(f"%{clean_q}%"),
            User.full_name.ilike(f"%{clean_q}%"),
            User.mobile.ilike(f"%{clean_q}%"),
            Resident.full_name.ilike(f"%{clean_q}%"),
            Resident.mobile.ilike(f"%{clean_q}%"),
            Flat.flat_number.ilike(f"%{clean_q}%"),
            Block.name.ilike(f"%{clean_q}%"),
            Building.name.ilike(f"%{clean_q}%"),
        ]
        if norm:
            conditions.append(Vehicle.normalized_number_plate.ilike(f"%{norm}%"))
            conditions.append(Vehicle.vehicle_number.ilike(f"%{norm}%"))

        db_results = q.filter(or_(*conditions)).order_by(Vehicle.created_at.desc()).all()

        seen_ids = {v.id for v in db_results}
        results = list(db_results)

        clean_upper = clean_q.upper()
        clean_no_space = re.sub(r"[\s\-_.\/]+", "", clean_upper)

        all_society_vehicles = Vehicle.query.filter_by(society_id=society_id)
        if active_only:
            all_society_vehicles = all_society_vehicles.filter(Vehicle.status == "ACTIVE")
        if type_clean and type_clean not in ["all", ""]:
            if type_clean in ["car", "cars"]:
                all_society_vehicles = all_society_vehicles.filter(Vehicle.vehicle_type.in_(["Car", "Electric Car"]))
            elif type_clean in ["bike", "bikes", "scooter", "two-wheeler", "two wheeler"]:
                all_society_vehicles = all_society_vehicles.filter(Vehicle.vehicle_type.in_(["Bike", "Scooter", "Electric Bike", "Cycle"]))
            elif type_clean in ["other", "others"]:
                all_society_vehicles = all_society_vehicles.filter(Vehicle.vehicle_type.in_(["Commercial Vehicle", "Other"]))
            else:
                all_society_vehicles = all_society_vehicles.filter(Vehicle.vehicle_type.ilike(f"%{vehicle_type.strip()}%"))

        for v in all_society_vehicles.all():
            if v.id in seen_ids:
                continue

            # Flat match (e.g. BLOCK A-101 vs A-101 vs 101)
            flat_pk = (v.flat.property_key if v.flat else "").upper()
            flat_no_space = re.sub(r"[\s\-_.\/]+", "", flat_pk)
            if flat_pk and (clean_upper in flat_pk or flat_pk in clean_upper or (clean_no_space and clean_no_space in flat_no_space)):
                results.append(v)
                seen_ids.add(v.id)
                continue

            # Normalized number plate match
            if norm:
                v_norm = cls.normalize_plate(v.vehicle_number)
                if norm in v_norm or v_norm in norm:
                    results.append(v)
                    seen_ids.add(v.id)
                    continue

            # Owner / Resident name or mobile fallback
            o_name = ((v.owner.full_name if v.owner else "") or (v.resident.full_name if v.resident else "")).upper()
            if clean_upper in o_name:
                results.append(v)
                seen_ids.add(v.id)
                continue

            o_mob = ((v.owner.mobile if v.owner else "") or (v.resident.mobile if v.resident else ""))
            if clean_q in o_mob:
                results.append(v)
                seen_ids.add(v.id)
                continue

        return results

    @classmethod
    def notify_vehicle_owner(cls, sender_user, vehicle_id, message_type, custom_note=None):
        """
        Sends an internal notification to the vehicle owner without leaking private contact information.
        """
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError("Vehicle not found.")

        if vehicle.society_id != sender_user.society_id and sender_user.role not in ["Super Admin"]:
            raise PermissionError("Unauthorized society access.")

        # Determine target user
        target_user_id = vehicle.owner_user_id
        if not target_user_id and vehicle.resident:
            target_user_id = vehicle.resident.user_id

        if not target_user_id:
            # Fallback to resident owner mobile if user_id is missing
            recipient = vehicle.resident.mobile if vehicle.resident else "N/A"
        else:
            target_user = db.session.get(User, target_user_id)
            recipient = target_user.mobile or target_user.email if target_user else "N/A"

        # Construct privacy-safe message
        plate = vehicle.vehicle_number

        type_messages = {
            "PARKING_ISSUE": f"A resident reported a parking issue regarding your vehicle {plate} in {vehicle.parking_slot_display}.",
            "REQUEST_CONTACT": f"A resident from your society is requesting contact regarding your vehicle {plate}.",
            "BLOCKING_VEHICLE": f"Your vehicle {plate} is currently reported as blocking access. Please check and move if necessary.",
            "LIGHTS_ON": f"A resident noticed the lights/windows on your vehicle {plate} might be left on.",
        }

        base_msg = type_messages.get(message_type, f"A community notice regarding your vehicle {plate}.")
        if custom_note and str(custom_note).strip():
            # Sanitize note
            clean_note = re.sub(r"[<>]", "", str(custom_note).strip())[:200]
            full_msg = f"{base_msg} Note: {clean_note}"
        else:
            full_msg = base_msg

        NotificationService.send_notification(
            recipient=recipient,
            message=full_msg,
            channel="In-App",
            subject=f"Vehicle Alert: {plate}",
            society_id=vehicle.society_id,
            user_id=target_user_id,
            category="General",
        )

        return True

    @staticmethod
    def get_safe_public_details(vehicle):
        """
        Extracts permitted community-visible details for authorized same-society residents.
        Includes contact phone numbers for calling when vehicle is active.
        """
        if not vehicle:
            return None

        owner_name = "Society Resident"
        flat_number = "-"

        if vehicle.owner and vehicle.owner.full_name and vehicle.owner.full_name.strip():
            owner_name = vehicle.owner.full_name.strip()
        elif vehicle.resident and vehicle.resident.full_name and vehicle.resident.full_name.strip():
            owner_name = vehicle.resident.full_name.strip()
        elif vehicle.flat:
            if vehicle.flat.active_resident and vehicle.flat.active_resident.full_name:
                owner_name = vehicle.flat.active_resident.full_name
            elif vehicle.flat.residents and len(vehicle.flat.residents) > 0 and vehicle.flat.residents[0].full_name:
                owner_name = vehicle.flat.residents[0].full_name

        if vehicle.flat:
            flat_number = vehicle.flat.property_key or vehicle.flat.flat_number

        phone = None
        if vehicle.owner:
            if vehicle.owner.mobile and vehicle.owner.mobile.strip():
                phone = vehicle.owner.mobile.strip()
        elif vehicle.resident:
            if vehicle.resident.mobile and vehicle.resident.mobile.strip():
                phone = vehicle.resident.mobile.strip()
        elif vehicle.flat:
            if vehicle.flat.active_resident and vehicle.flat.active_resident.mobile:
                phone = vehicle.flat.active_resident.mobile.strip()
            elif vehicle.flat.residents and len(vehicle.flat.residents) > 0 and vehicle.flat.residents[0].mobile:
                phone = vehicle.flat.residents[0].mobile.strip()

        secondary_phone = vehicle.secondary_mobile or None

        return {
            "id": vehicle.id,
            "vehicle_number": vehicle.vehicle_number,
            "vehicle_type": vehicle.vehicle_type or "Car",
            "make": vehicle.make or "-",
            "model": vehicle.model or "-",
            "brand_model": vehicle.brand_model or vehicle.make_model or "-",
            "color": vehicle.color or "-",
            "parking_slot": vehicle.parking_slot_display,
            "owner_name": owner_name,
            "flat_number": flat_number,
            "phone": phone,
            "secondary_phone": secondary_phone,
            "status": vehicle.status,
            "owner_user_id": vehicle.owner_user_id,
        }

    @staticmethod
    def allocate_parking_slot(slot_id, flat_id):
        """Allocates a parking slot to a flat, preventing double allocation."""
        slot = db.session.get(ParkingSlot, slot_id)
        if not slot:
            raise ValueError("Parking slot not found")

        if slot.flat_id and slot.flat_id != flat_id:
            raise ValueError(
                f"Parking slot {slot.slot_number} is already allocated to flat ID {slot.flat_id}"
            )

        slot.flat_id = flat_id
        slot.status = "Allocated"
        db.session.commit()
        return slot
