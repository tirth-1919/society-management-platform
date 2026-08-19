from app.models import (
    Resident,
    Building,
    Block,
    Flat,
    MaintenanceBill,
    Complaint,
    Visitor,
    Vehicle,
    Notice,
    Payment,
    PaymentReceipt,
    Vendor,
    Staff,
    ExpenseVoucher,
    Document,
    AuditLog,
    Role,
)


class SearchService:
    @staticmethod
    def global_search(user, society_id, query_str, category=None, limit=6):
        """
        Global search engine with role-aware privacy enforcement.
        Admins search society-wide records across all categories.
        Residents ONLY search their own bills, payments, receipts, complaints, visitors, vehicles, public documents, and public notices.
        Supports category filtering and result limits.
        """
        if not query_str or len(query_str.strip()) < 2:
            return {"query": query_str or "", "categories": []}

        q_clean = query_str.strip()
        q_lower = q_clean.lower()
        term = f"%{q_clean}%"
        limit = min(max(1, limit or 6), 50)
        is_resident = user.role in ["Resident", Role.RESIDENT]

        categories = []
        cat_filter = category.lower().strip() if category else None

        def should_include(cat_key):
            if not cat_filter:
                return True
            raw_key = cat_key.replace("category_", "").lower()
            filt = cat_filter.replace("category_", "").lower()
            return filt in raw_key or raw_key in filt

        if is_resident:
            # Find associated resident profile for logged-in resident user
            resident = Resident.query.filter_by(
                user_id=user.id, society_id=society_id
            ).first()

            if not resident:
                return {"query": query_str, "categories": []}

            # 1. Own Bills
            if should_include("category_bills"):
                own_bills = (
                    MaintenanceBill.query.filter_by(society_id=society_id, resident_id=resident.id)
                    .filter(
                        (MaintenanceBill.bill_number.ilike(term))
                        | (MaintenanceBill.billing_month.ilike(term))
                        | (MaintenanceBill.status.ilike(term))
                    )
                    .order_by(MaintenanceBill.billing_month.desc())
                    .limit(limit)
                    .all()
                )
                if own_bills:
                    categories.append({
                        "key": "category_bills",
                        "items": [
                            {
                                "id": b.id,
                                "title": f"Bill #{b.bill_number} - {b.billing_month}",
                                "subtitle": f"Amount: ₹{b.total_amount:,.2f} | Status: {b.status}",
                                "url": f"/resident/bills/{b.id}",
                                "icon": "fa-file-invoice"
                            }
                            for b in own_bills
                        ]
                    })

            # 2. Own Payments
            if should_include("category_payments"):
                own_payments = (
                    Payment.query.filter_by(society_id=society_id, resident_id=resident.id)
                    .filter(
                        (Payment.transaction_id.ilike(term))
                        | (Payment.payment_method.ilike(term))
                        | (Payment.status.ilike(term))
                    )
                    .order_by(Payment.payment_date.desc())
                    .limit(limit)
                    .all()
                )
                if own_payments:
                    categories.append({
                        "key": "category_payments",
                        "items": [
                            {
                                "id": p.id,
                                "title": f"Payment #{p.transaction_id or p.id}",
                                "subtitle": f"₹{p.amount_paid:,.2f} via {p.payment_method or 'Online'} ({p.status})",
                                "url": "/payments/payment_history",
                                "icon": "fa-receipt"
                            }
                            for p in own_payments
                        ]
                    })

            # 3. Own Receipts
            if should_include("category_receipts"):
                own_receipts = (
                    PaymentReceipt.query.join(Payment)
                    .filter(
                        Payment.resident_id == resident.id,
                        Payment.society_id == society_id,
                        (PaymentReceipt.receipt_number.ilike(term)) | (Payment.transaction_id.ilike(term)),
                    )
                    .order_by(PaymentReceipt.generated_at.desc())
                    .limit(limit)
                    .all()
                )
                if own_receipts:
                    categories.append({
                        "key": "category_receipts",
                        "items": [
                            {
                                "id": r.id,
                                "title": f"Receipt #{r.receipt_number}",
                                "subtitle": f"Generated: {r.generated_at.strftime('%Y-%m-%d') if r.generated_at else ''}",
                                "url": "/resident/receipts",
                                "icon": "fa-receipt"
                            }
                            for r in own_receipts
                        ]
                    })

            # 4. Own Complaints
            if should_include("category_complaints"):
                own_complaints = (
                    Complaint.query.filter_by(society_id=society_id, resident_id=resident.id)
                    .filter(
                        (Complaint.ticket_number.ilike(term))
                        | (Complaint.title.ilike(term))
                        | (Complaint.category.ilike(term))
                        | (Complaint.status.ilike(term))
                    )
                    .order_by(Complaint.created_at.desc())
                    .limit(limit)
                    .all()
                )
                if own_complaints:
                    categories.append({
                        "key": "category_complaints",
                        "items": [
                            {
                                "id": c.id,
                                "title": f"#{c.ticket_number} - {c.title}",
                                "subtitle": f"Category: {c.category} | Status: {c.status}",
                                "url": f"/complaints/{c.id}",
                                "icon": "fa-headset"
                            }
                            for c in own_complaints
                        ]
                    })

            # 5. Own Visitors
            if should_include("category_visitors"):
                own_visitors = (
                    Visitor.query.filter_by(society_id=society_id, resident_id=resident.id)
                    .filter(
                        (Visitor.visitor_name.ilike(term))
                        | (Visitor.mobile.ilike(term))
                        | (Visitor.purpose.ilike(term))
                    )
                    .order_by(Visitor.entry_time.desc())
                    .limit(limit)
                    .all()
                )
                if own_visitors:
                    categories.append({
                        "key": "category_visitors",
                        "items": [
                            {
                                "id": v.id,
                                "title": f"Visitor: {v.visitor_name}",
                                "subtitle": f"Purpose: {v.purpose or '-'} | Mobile: {v.mobile or '-'}",
                                "url": "/visitors/list",
                                "icon": "fa-id-badge"
                            }
                            for v in own_visitors
                        ]
                    })

            # 6. Own Vehicles
            if should_include("category_vehicles"):
                try:
                    own_vehicles = (
                        Vehicle.query.filter_by(society_id=society_id, flat_id=resident.flat_id)
                        .filter(
                            (Vehicle.vehicle_number.ilike(term))
                            | (Vehicle.vehicle_type.ilike(term))
                            | (Vehicle.make_model.ilike(term))
                        )
                        .limit(limit)
                        .all()
                    )
                    if own_vehicles:
                        categories.append({
                            "key": "category_vehicles",
                            "items": [
                                {
                                    "id": vh.id,
                                    "title": f"Vehicle #{vh.vehicle_number}",
                                    "subtitle": f"Type: {vh.vehicle_type} | Model: {vh.make_model or '-'}",
                                    "url": "/resident/profile",
                                    "icon": "fa-car"
                                }
                                for vh in own_vehicles
                            ]
                        })
                except Exception:
                    pass

            # 7. Public Notices / Announcements
            if should_include("category_notices"):
                notices = (
                    Notice.query.filter_by(society_id=society_id)
                    .filter(
                        (Notice.title.ilike(term))
                        | (Notice.content.ilike(term))
                        | (Notice.notice_type.ilike(term))
                    )
                    .order_by(Notice.created_at.desc() if hasattr(Notice, 'created_at') else Notice.id.desc())
                    .limit(limit)
                    .all()
                )
                if notices:
                    categories.append({
                        "key": "category_notices",
                        "items": [
                            {
                                "id": n.id,
                                "title": n.title,
                                "subtitle": f"Notice | Type: {n.notice_type}",
                                "url": "/resident/announcements",
                                "icon": "fa-bullhorn"
                            }
                            for n in notices
                        ]
                    })

            # 8. Public Documents
            if should_include("category_documents"):
                try:
                    public_docs = (
                        Document.query.filter_by(society_id=society_id, access_level="RESIDENT_PUBLIC")
                        .filter(
                            (Document.title.ilike(term))
                            | (Document.category.ilike(term))
                            | (Document.description.ilike(term))
                        )
                        .order_by(Document.created_at.desc())
                        .limit(limit)
                        .all()
                    )
                    if public_docs:
                        categories.append({
                            "key": "category_documents",
                            "items": [
                                {
                                    "id": d.id,
                                    "title": d.title,
                                    "subtitle": f"Category: {d.category}",
                                    "url": "/resident/documents",
                                    "icon": "fa-folder-open"
                                }
                                for d in public_docs
                            ]
                        })
                except Exception:
                    pass

        else:
            # ADMIN SEARCH (Super Admin, Society Admin, Accounting Staff, Security Staff)

            # 1. Residents
            if should_include("category_residents"):
                res_q = Resident.query.filter_by(society_id=society_id)
                if q_lower not in ["resident", "residents", "member", "members"]:
                    res_q = res_q.filter(
                        (Resident.full_name.ilike(term))
                        | (Resident.mobile.ilike(term))
                        | (Resident.email.ilike(term))
                        | (Resident.resident_type.ilike(term))
                    )
                residents = res_q.limit(limit).all()
                if residents:
                    categories.append({
                        "key": "category_residents",
                        "items": [
                            {
                                "id": r.id,
                                "title": r.full_name,
                                "subtitle": f"Mobile: {r.mobile or '-'} | Type: {r.resident_type}" + (f" | Flat: {r.flat.flat_number}" if r.flat else ""),
                                "url": "/admin/residents",
                                "icon": "fa-user"
                            }
                            for r in residents
                        ]
                    })

            # 2. Flats & Wings & Blocks
            if should_include("category_flats"):
                flat_q = Flat.query.filter_by(society_id=society_id)
                if q_lower in ["flat", "flats"]:
                    flats = flat_q.limit(limit).all()
                else:
                    flats = (
                        flat_q.outerjoin(Building, Flat.building_id == Building.id)
                        .outerjoin(Block, Flat.block_id == Block.id)
                        .filter(
                            (Flat.flat_number.ilike(term))
                            | (Flat.flat_type.ilike(term))
                            | (Flat.occupancy_status.ilike(term))
                            | (Building.name.ilike(term))
                            | (Block.name.ilike(term))
                        )
                        .limit(limit)
                        .all()
                    )
                if flats:
                    categories.append({
                        "key": "category_flats",
                        "items": [
                            {
                                "id": f.id,
                                "title": f"Flat {f.flat_number}" + (f" ({f.building.name})" if f.building else ""),
                                "subtitle": f"Floor: {f.floor_number} | Type: {f.flat_type} | Occupancy: {f.occupancy_status}",
                                "url": "/admin/flats",
                                "icon": "fa-building"
                            }
                            for f in flats
                        ]
                    })

            # 3. Bills
            if should_include("category_bills"):
                bills_q = MaintenanceBill.query.filter_by(society_id=society_id)
                if q_lower not in ["bill", "bills", "billing", "invoice"]:
                    bills_q = bills_q.filter(
                        (MaintenanceBill.bill_number.ilike(term))
                        | (MaintenanceBill.billing_month.ilike(term))
                        | (MaintenanceBill.status.ilike(term))
                    )
                bills = bills_q.order_by(MaintenanceBill.billing_month.desc()).limit(limit).all()
                if bills:
                    categories.append({
                        "key": "category_bills",
                        "items": [
                            {
                                "id": b.id,
                                "title": f"Bill #{b.bill_number} - {b.billing_month}",
                                "subtitle": f"Amount: ₹{b.total_amount:,.2f} | Status: {b.status}" + (f" | Flat {b.flat.flat_number}" if b.flat else ""),
                                "url": "/payments/bills",
                                "icon": "fa-file-invoice"
                            }
                            for b in bills
                        ]
                    })

            # 4. Payments
            if should_include("category_payments"):
                pay_q = Payment.query.filter_by(society_id=society_id)
                if q_lower not in ["payment", "payments", "transaction", "pay"]:
                    pay_q = pay_q.filter(
                        (Payment.transaction_id.ilike(term))
                        | (Payment.payment_method.ilike(term))
                        | (Payment.status.ilike(term))
                    )
                payments = pay_q.order_by(Payment.payment_date.desc()).limit(limit).all()
                if payments:
                    categories.append({
                        "key": "category_payments",
                        "items": [
                            {
                                "id": p.id,
                                "title": f"Payment TXN #{p.transaction_id or p.id}",
                                "subtitle": f"Paid: ₹{p.amount_paid:,.2f} via {p.payment_method or 'Online'} ({p.status})",
                                "url": "/payments/admin_dashboard",
                                "icon": "fa-receipt"
                            }
                            for p in payments
                        ]
                    })

            # 5. Complaints
            if should_include("category_complaints"):
                comp_q = Complaint.query.filter_by(society_id=society_id)
                if q_lower not in ["complaint", "complaints", "ticket", "tickets", "issue", "issues"]:
                    comp_q = comp_q.filter(
                        (Complaint.ticket_number.ilike(term))
                        | (Complaint.title.ilike(term))
                        | (Complaint.category.ilike(term))
                        | (Complaint.status.ilike(term))
                    )
                complaints = comp_q.order_by(Complaint.created_at.desc()).limit(limit).all()
                if complaints:
                    categories.append({
                        "key": "category_complaints",
                        "items": [
                            {
                                "id": c.id,
                                "title": f"#{c.ticket_number} - {c.title}",
                                "subtitle": f"Category: {c.category} | Status: {c.status}",
                                "url": f"/complaints/{c.id}",
                                "icon": "fa-headset"
                            }
                            for c in complaints
                        ]
                    })

            # 6. Visitors
            if should_include("category_visitors"):
                vis_q = Visitor.query.filter_by(society_id=society_id)
                if q_lower not in ["visitor", "visitors", "guest", "guests"]:
                    vis_q = vis_q.filter(
                        (Visitor.visitor_name.ilike(term))
                        | (Visitor.mobile.ilike(term))
                        | (Visitor.purpose.ilike(term))
                        | (Visitor.vehicle_number.ilike(term))
                    )
                visitors = vis_q.order_by(Visitor.entry_time.desc()).limit(limit).all()
                if visitors:
                    categories.append({
                        "key": "category_visitors",
                        "items": [
                            {
                                "id": v.id,
                                "title": f"Visitor: {v.visitor_name}",
                                "subtitle": f"Mobile: {v.mobile or '-'} | Purpose: {v.purpose or '-'}",
                                "url": "/visitors/list",
                                "icon": "fa-id-badge"
                            }
                            for v in visitors
                        ]
                    })

            # 7. Vehicles
            if should_include("category_vehicles"):
                try:
                    veh_q = Vehicle.query.filter_by(society_id=society_id)
                    if q_lower not in ["vehicle", "vehicles", "car", "bike", "parking"]:
                        veh_q = veh_q.filter(
                            (Vehicle.vehicle_number.ilike(term))
                            | (Vehicle.vehicle_type.ilike(term))
                            | (Vehicle.make_model.ilike(term))
                        )
                    vehicles = veh_q.limit(limit).all()
                    if vehicles:
                        categories.append({
                            "key": "category_vehicles",
                            "items": [
                                {
                                    "id": v.id,
                                    "title": f"Vehicle #{v.vehicle_number}",
                                    "subtitle": f"Type: {v.vehicle_type} | Model: {v.make_model or '-'}",
                                    "url": "/visitors/list",
                                    "icon": "fa-car"
                                }
                                for v in vehicles
                            ]
                        })
                except Exception:
                    pass

            # 8. Vendors & Operations
            if should_include("category_vendors"):
                try:
                    vnd_q = Vendor.query.filter_by(society_id=society_id)
                    if q_lower not in ["vendor", "vendors", "contractor", "amc"]:
                        vnd_q = vnd_q.filter(
                            (Vendor.company_name.ilike(term))
                            | (Vendor.contact_person.ilike(term))
                            | (Vendor.category.ilike(term))
                            | (Vendor.phone.ilike(term))
                        )
                    vendors = vnd_q.limit(limit).all()
                    if vendors:
                        categories.append({
                            "key": "category_vendors",
                            "items": [
                                {
                                    "id": vn.id,
                                    "title": f"Vendor: {vn.company_name}",
                                    "subtitle": f"Contact: {vn.contact_person} ({vn.category}) | Phone: {vn.phone}",
                                    "url": "/operations/vendors",
                                    "icon": "fa-handshake"
                                }
                                for vn in vendors
                            ]
                        })
                except Exception:
                    pass

            # 9. Staff
            if should_include("category_staff"):
                try:
                    stf_q = Staff.query.filter_by(society_id=society_id)
                    if q_lower not in ["staff", "employee", "guard"]:
                        stf_q = stf_q.filter(
                            (Staff.full_name.ilike(term))
                            | (Staff.role_type.ilike(term))
                            | (Staff.phone.ilike(term))
                        )
                    staff_members = stf_q.limit(limit).all()
                    if staff_members:
                        categories.append({
                            "key": "category_staff",
                            "items": [
                                {
                                    "id": st.id,
                                    "title": f"Staff: {st.full_name}",
                                    "subtitle": f"Role: {st.role_type} | Phone: {st.phone}",
                                    "url": "/operations/vendors",
                                    "icon": "fa-user-gear"
                                }
                                for st in staff_members
                            ]
                        })
                except Exception:
                    pass

            # 10. Expenses & Accounting Vouchers
            if should_include("category_expenses"):
                try:
                    exp_q = ExpenseVoucher.query.filter_by(society_id=society_id)
                    if q_lower not in ["expense", "expenses", "voucher", "vouchers", "spending"]:
                        exp_q = exp_q.filter(
                            (ExpenseVoucher.voucher_number.ilike(term))
                            | (ExpenseVoucher.payee_name.ilike(term))
                            | (ExpenseVoucher.category.ilike(term))
                            | (ExpenseVoucher.description.ilike(term))
                        )
                    expenses = exp_q.order_by(ExpenseVoucher.voucher_date.desc() if hasattr(ExpenseVoucher, 'voucher_date') else ExpenseVoucher.id.desc()).limit(limit).all()
                    if expenses:
                        categories.append({
                            "key": "category_expenses",
                            "items": [
                                {
                                    "id": ex.id,
                                    "title": f"Voucher #{ex.voucher_number}",
                                    "subtitle": f"Payee: {ex.payee_name} | Amount: ₹{ex.amount:,.2f} ({ex.category})",
                                    "url": "/accounting/vouchers",
                                    "icon": "fa-file-invoice-dollar"
                                }
                                for ex in expenses
                            ]
                        })
                except Exception:
                    pass

            # 11. Documents
            if should_include("category_documents"):
                try:
                    doc_q = Document.query.filter_by(society_id=society_id)
                    if q_lower not in ["document", "documents", "vault", "file", "files"]:
                        doc_q = doc_q.filter(
                            (Document.title.ilike(term))
                            | (Document.category.ilike(term))
                            | (Document.description.ilike(term))
                        )
                    docs = doc_q.order_by(Document.created_at.desc()).limit(limit).all()
                    if docs:
                        categories.append({
                            "key": "category_documents",
                            "items": [
                                {
                                    "id": doc.id,
                                    "title": doc.title,
                                    "subtitle": f"Category: {doc.category} | Access: {doc.access_level}",
                                    "url": "/documents/vault",
                                    "icon": "fa-vault"
                                }
                                for doc in docs
                            ]
                        })
                except Exception:
                    pass

            # 12. Notices
            if should_include("category_notices"):
                notices_q = Notice.query.filter_by(society_id=society_id)
                if q_lower not in ["notice", "notices", "announcement", "announcements", "circular"]:
                    notices_q = notices_q.filter(
                        (Notice.title.ilike(term))
                        | (Notice.content.ilike(term))
                        | (Notice.notice_type.ilike(term))
                    )
                notices = notices_q.order_by(Notice.created_at.desc() if hasattr(Notice, 'created_at') else Notice.id.desc()).limit(limit).all()
                if notices:
                    categories.append({
                        "key": "category_notices",
                        "items": [
                            {
                                "id": n.id,
                                "title": n.title,
                                "subtitle": f"Notice | Type: {n.notice_type}",
                                "url": "/resident/announcements",
                                "icon": "fa-bullhorn"
                            }
                            for n in notices
                        ]
                    })

            # 13. Audit Logs
            if should_include("category_audit"):
                try:
                    audit_q = AuditLog.query.filter_by(society_id=society_id)
                    if q_lower not in ["audit", "audits", "log", "logs", "activity"]:
                        audit_q = audit_q.filter(
                            (AuditLog.action.ilike(term))
                            | (AuditLog.details.ilike(term))
                        )
                    audit_logs = audit_q.order_by(AuditLog.created_at.desc()).limit(limit).all()
                    if audit_logs:
                        categories.append({
                            "key": "category_audit",
                            "items": [
                                {
                                    "id": log.id,
                                    "title": f"Audit Log: {log.action}",
                                    "subtitle": f"Details: {log.details or '-'} | {log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else ''}",
                                    "url": "/system/backups",
                                    "icon": "fa-clock-rotate-left"
                                }
                                for log in audit_logs
                            ]
                        })
                except Exception:
                    pass

        return {"query": query_str, "categories": categories}
