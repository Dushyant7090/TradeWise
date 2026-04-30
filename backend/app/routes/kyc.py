"""
KYC routes
- GET    /api/pro-trader/kyc/status
- POST   /api/pro-trader/kyc/documents/upload
- GET    /api/pro-trader/kyc/documents
- DELETE /api/pro-trader/kyc/documents/{id}
- GET    /api/pro-trader/bank-details
- PUT    /api/pro-trader/bank-details
- POST   /api/pro-trader/kyc/submit-review
"""
import logging
import mimetypes
import uuid
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_pro_trader
from app.models.pro_trader_profile import ProTraderProfile
from app.utils.encryption import encrypt_value, mask_account_number
from app.utils.validators import validate_ifsc_code

logger = logging.getLogger(__name__)
kyc_bp = Blueprint("kyc", __name__)


@kyc_bp.route("/kyc/status", methods=["GET"])
@require_pro_trader
def get_kyc_status():
    """Get full KYC + setup status for the dynamic kyc-setup page."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    # Fetch subscription plans
    from app.models import SubscriptionPlan
    plans = SubscriptionPlan.query.filter_by(trader_id=user_id, is_active=True).all()

    return jsonify({
        "kyc_status": pt_profile.kyc_status,
        "kyc_documents": pt_profile.kyc_documents or {},
        "kyc_rejection_reason": getattr(pt_profile, "kyc_rejection_reason", None),
        "has_bank_details": bool(pt_profile.bank_account_number_encrypted),
        "bank_account_last_4": pt_profile.bank_account_last_4,
        "ifsc_code": pt_profile.ifsc_code,
        "account_holder_name": pt_profile.account_holder_name,
        "onboarding_step": getattr(pt_profile, "onboarding_step", 0),
        "is_review_pending": getattr(pt_profile, "is_review_pending", False),
        "subscription_plans": [p.to_dict() for p in plans],
        "monthly_subscription_price": float(pt_profile.monthly_subscription_price or 0),
    }), 200


@kyc_bp.route("/kyc/documents/upload", methods=["POST"])
@require_pro_trader
def upload_kyc_document():
    """Upload a KYC document to Supabase Storage."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    file = request.files.get("document") or request.files.get("file")
    if file is None:
        return jsonify({"error": "No document file provided"}), 400

    doc_type = request.form.get("document_type", "").strip().lower()
    doc_type_aliases = {
        "pan_card": "pan",
        "id_proof": "aadhaar",
    }
    doc_type = doc_type_aliases.get(doc_type, doc_type)

    valid_doc_types = ["aadhaar", "pan", "passport", "voter_id", "driving_license", "bank_statement"]
    if not doc_type or doc_type not in valid_doc_types:
        return jsonify({
            "error": f"document_type must be one of: {valid_doc_types}"
        }), 400

    if not file.filename:
        return jsonify({"error": "Empty file"}), 400

    allowed_types = {"image/jpeg", "image/jpg", "image/pjpeg", "image/png", "application/pdf"}
    content_type = (file.content_type or "").lower().strip()
    if not content_type:
        content_type = (mimetypes.guess_type(file.filename)[0] or "").lower().strip()
    if content_type not in allowed_types:
        return jsonify({"error": "Invalid file type. Use JPEG, PNG, or PDF"}), 400

    file_data = file.read()
    if len(file_data) > 10 * 1024 * 1024:  # 10 MB
        return jsonify({"error": "File too large. Max 10MB"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    doc_id = str(uuid.uuid4())
    filename = f"kyc/{user_id}/{doc_type}/{doc_id}.{ext}"

    try:
        from app.services.supabase_storage import supabase_storage
        bucket = current_app.config.get("KYC_DOCUMENTS_BUCKET", "kyc-documents")
        url = supabase_storage.upload_file(
            bucket=bucket,
            path=filename,
            file_data=file_data,
            content_type=content_type or "application/octet-stream",
        )

        # Store in kyc_documents JSON (copy to avoid in-place mutation tracking issues)
        docs = dict(pt_profile.kyc_documents or {})
        docs[doc_id] = {
            "id": doc_id,
            "type": doc_type,
            "url": url,
            "filename": file.filename,
            "content_type": content_type,
            "storage_path": filename,
            "uploaded_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
        pt_profile.kyc_documents = docs
        db.session.commit()

        return jsonify({
            "message": "Document uploaded successfully",
            "document": docs[doc_id],
        }), 201
    except Exception as e:
        logger.error(f"KYC document upload error: {e}")
        return jsonify({"error": "Failed to upload document"}), 500


@kyc_bp.route("/kyc/documents", methods=["GET"])
@require_pro_trader
def get_kyc_documents():
    """Get list of uploaded KYC documents."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    docs = pt_profile.kyc_documents or {}
    return jsonify({"documents": list(docs.values())}), 200


@kyc_bp.route("/kyc/documents/<doc_id>", methods=["DELETE"])
@require_pro_trader
def delete_kyc_document(doc_id):
    """Delete a KYC document."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    if pt_profile.kyc_status == "verified":
        return jsonify({"error": "Cannot delete documents after KYC is verified"}), 400

    docs = dict(pt_profile.kyc_documents or {})
    if doc_id not in docs:
        return jsonify({"error": "Document not found"}), 404

    doc = docs[doc_id]
    # Delete from Supabase Storage
    try:
        from app.services.supabase_storage import supabase_storage
        bucket = current_app.config.get("KYC_DOCUMENTS_BUCKET", "kyc-documents")
        supabase_storage.delete_file(
            bucket=bucket,
            path=doc.get("storage_path", ""),
        )
    except Exception as e:
        logger.error(f"Failed to delete KYC document from storage: {e}")

    del docs[doc_id]
    pt_profile.kyc_documents = docs
    db.session.commit()

    return jsonify({"message": "Document deleted successfully"}), 200


@kyc_bp.route("/bank-details", methods=["GET"])
@require_pro_trader
def get_bank_details():
    """Get masked bank details."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify({
        "bank_account_last_4": pt_profile.bank_account_last_4,
        "ifsc_code": pt_profile.ifsc_code,
        "account_holder_name": pt_profile.account_holder_name,
        "has_bank_details": bool(pt_profile.bank_account_number_encrypted),
    }), 200


@kyc_bp.route("/bank-details", methods=["PUT"])
@require_pro_trader
def update_bank_details():
    """Update bank account details (stored encrypted)."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    data = request.get_json() or {}
    account_number = data.get("bank_account_number", "").strip()
    ifsc_code = data.get("ifsc_code", "").strip().upper()
    account_holder_name = data.get("account_holder_name", "").strip()

    if not account_number or not ifsc_code or not account_holder_name:
        return jsonify({"error": "bank_account_number, ifsc_code, and account_holder_name are required"}), 400

    if not account_number.isdigit() or len(account_number) < 9 or len(account_number) > 18:
        return jsonify({"error": "Invalid bank account number"}), 400

    if not validate_ifsc_code(ifsc_code):
        return jsonify({"error": "Invalid IFSC code format (e.g., SBIN0001234)"}), 400

    pt_profile.bank_account_number_encrypted = encrypt_value(account_number)
    pt_profile.bank_account_last_4 = account_number[-4:]
    pt_profile.ifsc_code = ifsc_code
    pt_profile.account_holder_name = account_holder_name
    db.session.commit()

    return jsonify({
        "message": "Bank details updated successfully",
        "bank_account_last_4": pt_profile.bank_account_last_4,
        "ifsc_code": ifsc_code,
        "account_holder_name": account_holder_name,
    }), 200


@kyc_bp.route("/kyc/submit-review", methods=["POST"])
@require_pro_trader
def submit_kyc_review():
    """Submit KYC for admin review."""
    user_id = get_jwt_identity()
    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    if not pt_profile:
        return jsonify({"error": "Profile not found"}), 404

    if pt_profile.kyc_status == "verified":
        return jsonify({"error": "KYC is already verified"}), 400

    docs = pt_profile.kyc_documents or {}
    if not docs:
        return jsonify({"error": "Please upload at least one KYC document before submitting for review"}), 400

    if not pt_profile.bank_account_number_encrypted:
        return jsonify({"error": "Please add bank details before submitting KYC"}), 400

    pt_profile.kyc_status = "pending"
    db.session.commit()

    return jsonify({
        "message": "KYC submitted for admin review",
        "kyc_status": pt_profile.kyc_status,
    }), 200
