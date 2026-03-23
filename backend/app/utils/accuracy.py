"""
Accuracy and performance calculation utilities
"""
from app import db
from app.models.pro_trader_profile import ProTraderProfile


def recalculate_accuracy(trader_id: str) -> float:
    """
    Recalculate accuracy score for a trader.
    accuracy = (winning_trades / total_trades) * 100
    If flag_count >= threshold, deduct FLAG_ACCURACY_PENALTY %.
    """
    from flask import current_app
    from app.models.trade import Trade

    profile = ProTraderProfile.query.filter_by(user_id=trader_id).first()
    if not profile:
        return 0.0

    # Count closed trades (target_hit = win, sl_hit = loss)
    total = db.session.query(Trade).filter(
        Trade.trader_id == trader_id,
        Trade.status.in_(["target_hit", "sl_hit"])
    ).count()

    wins = db.session.query(Trade).filter(
        Trade.trader_id == trader_id,
        Trade.status == "target_hit"
    ).count()

    if total == 0:
        profile.total_trades = 0
        profile.winning_trades = 0
        profile.accuracy_score = 0.0
        db.session.commit()
        return 0.0

    accuracy = (wins / total) * 100.0

    # Check total flag count against all active/closed trades
    flag_threshold = current_app.config.get("MAX_FLAG_PENALTY_THRESHOLD", 10)
    penalty = current_app.config.get("FLAG_ACCURACY_PENALTY", 5.0)

    heavily_flagged = db.session.query(Trade).filter(
        Trade.trader_id == trader_id,
        Trade.flag_count >= flag_threshold
    ).count()

    if heavily_flagged > 0:
        accuracy = max(0.0, accuracy - penalty * heavily_flagged)

    profile.total_trades = total
    profile.winning_trades = wins
    profile.accuracy_score = round(accuracy, 2)
    db.session.commit()

    # Update leaderboard rank after recalculation
    update_leaderboard_ranks()
    return accuracy


def update_leaderboard_ranks():
    """Recompute leaderboard ranks for all active pro traders sorted by accuracy."""
    traders = (
        ProTraderProfile.query
        .filter_by(is_active=True)
        .order_by(ProTraderProfile.accuracy_score.desc())
        .all()
    )
    for rank, trader in enumerate(traders, start=1):
        trader.leaderboard_rank = rank
    db.session.commit()


def calculate_rrr(direction: str, entry: float, stop_loss: float, target: float) -> float:
    """Calculate Risk-Reward Ratio."""
    if direction.lower() == "buy":
        risk = entry - stop_loss
        reward = target - entry
    else:
        risk = stop_loss - entry
        reward = entry - target

    if risk <= 0:
        return 0.0
    return round(reward / risk, 4)
