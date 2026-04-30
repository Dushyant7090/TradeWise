"""
Pro-Trader State Utility — canonical state derivation and eligibility checks.

Single source of truth for:
  EXPLORER  — onboarding_step >= 1, is_verified = False
  PENDING   — onboarding_step = 3, is_review_pending = True, is_verified = False
  VERIFIED  — is_verified = True

Usage:
    from app.utils.pro_trader_state import get_pro_trader_state, check_pending_eligibility
"""


def get_pro_trader_state(profile, pt_profile):
    """
    Derive the canonical pro-trader state from profile + pro_trader_profile data.

    Args:
        profile:    Profile model instance (has is_verified)
        pt_profile: ProTraderProfile model instance (has onboarding_step, is_review_pending)

    Returns:
        str: One of "NEW", "EXPLORER", "PENDING", "VERIFIED"
    """
    if profile and profile.is_verified:
        return "VERIFIED"

    if pt_profile and pt_profile.is_review_pending and pt_profile.onboarding_step >= 3:
        return "PENDING"

    if pt_profile and pt_profile.onboarding_step >= 1:
        return "EXPLORER"

    return "NEW"


def check_pending_eligibility(pt_profile):
    """
    Check whether a pro-trader meets all requirements to transition to PENDING state.

    Requirements:
      1. Step 1 complete (onboarding_step >= 1: bio/profile filled)
      2. Financial setup done (cf_seller_id set OR bank details present)
      3. Pricing/storefront submitted (onboarding_step >= 3)
      4. KYC documents uploaded (at least one document)
      5. Bank details present

    Args:
        pt_profile: ProTraderProfile model instance

    Returns:
        tuple: (eligible: bool, missing: list[str])
            eligible — True if all requirements met
            missing  — list of human-readable missing requirements
    """
    missing = []

    if not pt_profile:
        return False, ["Pro trader profile not found"]

    # Step 1: Profile basics
    if pt_profile.onboarding_step < 1:
        missing.append("Complete your profile (Step 1)")

    # Financial setup: either a Cashfree seller ID or bank details
    has_financial = bool(pt_profile.cf_seller_id) or bool(pt_profile.bank_account_number_encrypted)
    if not has_financial:
        missing.append("Complete financial setup (Step 2) or add bank details via KYC Setup")

    # KYC documents
    docs = pt_profile.kyc_documents or {}
    if not docs or (isinstance(docs, dict) and len(docs) == 0):
        missing.append("Upload at least one KYC document")

    # Bank details specifically (needed for payouts)
    if not pt_profile.bank_account_number_encrypted:
        missing.append("Add bank account details")

    eligible = len(missing) == 0
    return eligible, missing


def get_state_response(profile, pt_profile):
    """
    Build a full state response dict suitable for API responses.

    Args:
        profile:    Profile model instance
        pt_profile: ProTraderProfile model instance

    Returns:
        dict with state info
    """
    state = get_pro_trader_state(profile, pt_profile)

    result = {
        "state": state,
        "onboarding_step": pt_profile.onboarding_step if pt_profile else 0,
        "is_verified": profile.is_verified if profile else False,
        "is_review_pending": pt_profile.is_review_pending if pt_profile else False,
        "has_cf_seller_id": bool(pt_profile.cf_seller_id) if pt_profile else False,
        "has_bank_details": bool(pt_profile.bank_account_number_encrypted) if pt_profile else False,
        "has_kyc_documents": bool(pt_profile.kyc_documents) and len(pt_profile.kyc_documents or {}) > 0 if pt_profile else False,
        "kyc_status": pt_profile.kyc_status if pt_profile else "pending",
    }

    # Include eligibility info for non-verified users
    if state != "VERIFIED" and pt_profile:
        eligible, missing = check_pending_eligibility(pt_profile)
        result["pending_eligible"] = eligible
        result["pending_missing"] = missing

    return result
