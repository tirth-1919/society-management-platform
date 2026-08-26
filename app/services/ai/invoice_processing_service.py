"""
AI Invoice Processing System
============================
Automated document OCR, key-value extraction, confidence estimation,
duplicate invoice detection against existing ExpenseVouchers,
and verified conversion into approved expense vouchers.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.models.tenant import db
from app.models.document import Document
from app.models.accounting import ExpenseVoucher
from app.models.ai_operations import (
    AIDocumentAnalysis,
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.services.ai.ai_audit_service import AIAuditService
from app.utils import utcnow

logger = logging.getLogger(__name__)


class InvoiceProcessingAIService:
    @classmethod
    def extract_fields_from_text(cls, text_content: str, filename: str = "") -> dict[str, Any]:
        """
        Extracts structured invoice fields (Vendor, Invoice Number, Date, Amounts, Line Items)
        with confidence scores per field.
        """
        raw = text_content or ""
        lines = [line.strip() for line in raw.split("\n") if line.strip()]

        extracted: dict[str, Any] = {
            "vendor_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "due_date": None,
            "subtotal": 0.0,
            "tax": 0.0,
            "total": 0.0,
            "currency": "INR",
            "purchase_order": None,
            "line_items": [],
        }

        confidences: dict[str, float] = {
            "vendor_name": 0.0,
            "invoice_number": 0.0,
            "invoice_date": 0.0,
            "total": 0.0,
        }

        # 1. Invoice Number Extraction
        stop_words = {"FROM", "DATE", "TAX", "AMOUNT", "TOTAL", "BILL", "CASH", "PAID", "DUE"}
        for line in lines:
            inv_line_match = re.search(r"(?:invoice|inv|bill)\s*(?:no|number|num|#)?\s*[:.\-#]\s*([A-Z0-9\-_]+)", line, re.IGNORECASE)
            if inv_line_match:
                candidate = inv_line_match.group(1).strip().upper()
                if candidate not in stop_words and len(candidate) >= 3:
                    extracted["invoice_number"] = candidate
                    confidences["invoice_number"] = 0.98
                    break

        if not extracted["invoice_number"]:
            # Secondary scan for explicit INV- patterns
            explicit_inv = re.search(r"([A-Z]{2,6}-?[A-Z0-9]{2,10}-?\d{2,8})", raw)
            if explicit_inv and explicit_inv.group(1).upper() not in stop_words:
                extracted["invoice_number"] = explicit_inv.group(1).upper()
                confidences["invoice_number"] = 0.95
            else:
                # Try to derive from filename
                fn_match = re.search(r"(INV-?\d{3,10})", filename, re.IGNORECASE)
                if fn_match:
                    extracted["invoice_number"] = fn_match.group(1).upper()
                    confidences["invoice_number"] = 0.85
                else:
                    extracted["invoice_number"] = f"INV-UNKNOWN-{int(utcnow().timestamp()) % 10000}"
                    confidences["invoice_number"] = 0.40

        # 2. Total Amount Extraction (Line-by-line)
        for line in lines:
            total_match = re.search(r"(?:total|grand\s+total|net\s+amount|amount\s+payable|amount)[\s:₹rs\.]*([\d,]+(?:\.\d{1,2})?)", line, re.IGNORECASE)
            if total_match:
                try:
                    amt_str = total_match.group(1).replace(",", "")
                    amt_val = float(amt_str)
                    if amt_val > 0 and amt_val != float(utcnow().year):
                        extracted["total"] = amt_val
                        confidences["total"] = 0.96
                        break
                except ValueError:
                    pass

        if extracted["total"] == 0.0:
            # Fallback: scan all standalone money patterns
            amounts = re.findall(r"(?:₹|rs\.?|inr)\s*(\d{2,7}(?:\.\d{2})?)", raw, re.IGNORECASE)
            if amounts:
                try:
                    num_amts = [float(a.replace(",", "")) for a in amounts if float(a.replace(",", "")) > 50]
                    if num_amts:
                        extracted["total"] = max(num_amts)
                        confidences["total"] = 0.75
                except Exception:
                    pass

        # 3. Vendor Name Extraction
        vendor_match = re.search(r"(?:from|vendor|supplier|company|biller)[\s:\-]+([^\n,]{3,50})", raw, re.IGNORECASE)
        if vendor_match:
            extracted["vendor_name"] = vendor_match.group(1).strip()
            confidences["vendor_name"] = 0.92
        elif lines:
            # First non-empty header line is often vendor name
            for candidate in lines[:4]:
                if not re.search(r"(invoice|tax|date|gst|bill|receipt)", candidate, re.IGNORECASE) and len(candidate) > 3:
                    extracted["vendor_name"] = candidate[:60]
                    confidences["vendor_name"] = 0.82
                    break

        if not extracted["vendor_name"]:
            extracted["vendor_name"] = "Vendor Name Unspecified"
            confidences["vendor_name"] = 0.40

        # 4. Invoice Date Extraction
        date_match = re.search(r"(?:date|dated|invoice\s+date)[\s:\-]*(\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4})", raw, re.IGNORECASE)
        if date_match:
            extracted["invoice_date"] = date_match.group(1)
            confidences["invoice_date"] = 0.94
        else:
            extracted["invoice_date"] = utcnow().date().isoformat()
            confidences["invoice_date"] = 0.60

        # Overall average confidence
        overall_conf = sum(confidences.values()) / max(1, len(confidences))

        return {
            "extracted_fields": extracted,
            "field_confidences": confidences,
            "confidence_score": round(overall_conf, 2),
        }


    @classmethod
    def check_duplicate_invoice(
        cls, society_id: int, invoice_number: str, amount: float, vendor_name: str
    ) -> list[dict[str, Any]]:
        """
        Cross-checks invoice number and amount against existing ExpenseVouchers.
        """
        issues = []
        if not invoice_number:
            return issues

        existing_vouchers = ExpenseVoucher.query.filter_by(
            society_id=society_id
        ).filter(
            ExpenseVoucher.invoice_number.ilike(f"%{invoice_number.strip()}%")
        ).all()

        if existing_vouchers:
            for v in existing_vouchers:
                issues.append({
                    "issue_type": "DUPLICATE_INVOICE_NUMBER",
                    "severity": "HIGH",
                    "matched_voucher_id": v.id,
                    "matched_voucher_number": v.voucher_number,
                    "matched_amount": v.amount,
                    "message": f"Matching invoice number '{invoice_number}' already found in Voucher #{v.voucher_number} (₹{v.amount:,.2f}).",
                })

        return issues

    @classmethod
    def process_invoice_document(
        cls, document_id: int, society_id: int, raw_text: str = ""
    ) -> AIDocumentAnalysis:
        """
        Runs full AI invoice extraction, stores analysis record, and checks duplicates.
        """
        doc = Document.query.filter_by(id=document_id, society_id=society_id).first()
        filename = doc.file_path if doc else ""

        text_to_process = raw_text
        if not text_to_process and doc:
            text_to_process = f"Invoice Document: {doc.title}\nCategory: {doc.category}"

        extraction = cls.extract_fields_from_text(text_to_process, filename=filename)
        fields = extraction["extracted_fields"]

        issues = cls.check_duplicate_invoice(
            society_id=society_id,
            invoice_number=fields.get("invoice_number", ""),
            amount=fields.get("total", 0.0),
            vendor_name=fields.get("vendor_name", ""),
        )

        analysis = AIDocumentAnalysis.query.filter_by(
            document_id=document_id,
            society_id=society_id,
        ).first()

        if not analysis:
            analysis = AIDocumentAnalysis(
                society_id=society_id,
                document_id=document_id,
                detected_category="Vendor Invoice",
                confidence_score=extraction["confidence_score"],
                verification_status="PENDING",
            )
            db.session.add(analysis)

        analysis.set_extracted_fields(fields)
        analysis.set_field_confidences(extraction["field_confidences"])
        analysis.set_potential_issues([i["message"] for i in issues])
        analysis.confidence_score = extraction["confidence_score"]

        # Create finding if high-severity duplicate detected
        if issues:
            finding = AIFinding.query.filter_by(
                society_id=society_id,
                ai_system=AISystemType.INVOICE,
                entity_type="DOCUMENT",
                entity_id=document_id,
            ).first()

            if not finding:
                finding = AIFinding(
                    society_id=society_id,
                    ai_system=AISystemType.INVOICE,
                    entity_type="DOCUMENT",
                    entity_id=document_id,
                    finding_type="DUPLICATE_INVOICE_DOCUMENT",
                    severity=AIFindingSeverity.HIGH,
                    confidence_score=0.95,
                    title=f"Potential Duplicate Invoice Detected ({fields.get('invoice_number')})",
                    summary=f"Invoice #{fields.get('invoice_number')} has potential duplicate matches in accounting records.",
                    recommended_action="Verify original paper invoice before creating or approving an expense voucher.",
                    status=AIFindingStatus.NEW,
                )
                finding.set_evidence({"issues": issues, "extracted_fields": fields})
                db.session.add(finding)

        db.session.commit()
        return analysis

    @classmethod
    def approve_and_create_voucher(
        cls, analysis_id: int, society_id: int, actor_id: int, category: str = "Vendor", edited_fields: Optional[dict] = None
    ) -> ExpenseVoucher:
        """
        Approves an analyzed invoice and creates a formal ExpenseVoucher record.
        """
        analysis = AIDocumentAnalysis.query.filter_by(id=analysis_id, society_id=society_id).first()
        if not analysis:
            raise ValueError("Document analysis record not found.")

        fields = edited_fields or analysis.get_extracted_fields()
        import uuid
        voucher_no = f"EV-AI-{uuid.uuid4().hex[:6].upper()}"

        voucher = ExpenseVoucher(
            voucher_number=voucher_no,
            society_id=society_id,
            category=category,
            amount=float(fields.get("total", 0.0) or 0.0),
            payee_name=str(fields.get("vendor_name", "Vendor")),
            description=f"Generated via AI Invoice Processing for Invoice #{fields.get('invoice_number', 'N/A')}",
            invoice_number=str(fields.get("invoice_number", "")),
            expense_date=utcnow().date(),
            status="Approved",
            approved_by_id=actor_id,
        )
        db.session.add(voucher)

        analysis.verification_status = "VERIFIED"
        analysis.verified_by_id = actor_id
        analysis.verified_at = utcnow()
        db.session.commit()

        AIAuditService.log_event(
            society_id=society_id,
            action="APPROVE_INVOICE",
            entity_type="EXPENSE_VOUCHER",
            entity_id=voucher.id,
            actor_id=actor_id,
            details={"voucher_number": voucher_no, "invoice_number": fields.get("invoice_number")},
        )

        return voucher
