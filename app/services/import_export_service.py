import csv
import io
from app.models import db, Flat, Resident


class ImportExportService:
    @staticmethod
    def import_residents_csv(society_id, csv_text):
        """
        Parses CSV, validates fields, and imports residents transactionally.
        Rolls back completely if malformed.
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        imported_count = 0
        errors = []

        try:
            for idx, row in enumerate(reader, start=1):
                flat_num = row.get("flat_number")
                name = row.get("full_name")
                mobile = row.get("mobile")
                res_type = row.get("resident_type", "Owner")

                if not flat_num or not name or not mobile:
                    errors.append(
                        f"Row {idx}: Missing required fields (flat_number, full_name, mobile)"
                    )
                    continue

                flat = Flat.query.filter_by(
                    society_id=society_id, flat_number=flat_num
                ).first()
                if not flat:
                    errors.append(f"Row {idx}: Flat {flat_num} not found in society")
                    continue

                resident = Resident(
                    society_id=society_id,
                    flat_id=flat.id,
                    full_name=name,
                    mobile=mobile,
                    resident_type=res_type,
                    is_primary=True,
                )
                db.session.add(resident)
                imported_count += 1

            if errors:
                db.session.rollback()
                return False, errors, 0

            db.session.commit()
            return True, [], imported_count

        except Exception as e:
            db.session.rollback()
            return False, [str(e)], 0

    @staticmethod
    def export_residents_csv(society_id):
        """Exports residents data to CSV format."""
        residents = Resident.query.filter_by(society_id=society_id).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["ID", "Flat Number", "Full Name", "Mobile", "Email", "Type", "Status"]
        )

        for r in residents:
            writer.writerow(
                [
                    r.id,
                    r.flat.flat_number if r.flat else "N/A",
                    r.full_name,
                    r.mobile,
                    r.email or "",
                    r.resident_type,
                    r.occupancy_status,
                ]
            )

        return output.getvalue()
