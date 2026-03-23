"""
Comments routes
- GET  /api/pro-trader/trades/{id}/comments
- POST /api/pro-trader/trades/{id}/comments
- PUT  /api/pro-trader/trades/{id}/comments/{comment_id}
- DELETE /api/pro-trader/trades/{id}/comments/{comment_id}
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app import db
from app.middleware import require_auth
from app.models.comment import Comment
from app.models.trade import Trade

logger = logging.getLogger(__name__)
comments_bp = Blueprint("comments", __name__)


@comments_bp.route("/trades/<trade_id>/comments", methods=["GET"])
@require_auth
def get_comments(trade_id):
    """Get comments for a trade."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    query = Comment.query.filter_by(trade_id=trade_id).order_by(Comment.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    comments = []
    for c in paginated.items:
        comment_dict = c.to_dict()
        if c.user:
            from app.models.profile import Profile
            prof = Profile.query.filter_by(user_id=c.user_id).first()
            comment_dict["author"] = prof.display_name if prof else "Unknown"
        comments.append(comment_dict)

    return jsonify({
        "comments": comments,
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }), 200


@comments_bp.route("/trades/<trade_id>/comments", methods=["POST"])
@require_auth
def post_comment(trade_id):
    """Post a comment on a trade."""
    user_id = get_jwt_identity()

    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"error": "Trade not found"}), 404

    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Comment content is required"}), 400
    if len(content) > 2000:
        return jsonify({"error": "Comment too long (max 2000 chars)"}), 400

    comment = Comment(trade_id=trade_id, user_id=user_id, content=content)
    db.session.add(comment)
    db.session.commit()

    return jsonify({"message": "Comment posted", "comment": comment.to_dict()}), 201


@comments_bp.route("/trades/<trade_id>/comments/<comment_id>", methods=["PUT"])
@require_auth
def edit_comment(trade_id, comment_id):
    """Edit a comment (only the author can edit)."""
    user_id = get_jwt_identity()

    comment = Comment.query.filter_by(id=comment_id, trade_id=trade_id).first()
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    if comment.user_id != user_id:
        return jsonify({"error": "You can only edit your own comments"}), 403

    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Content is required"}), 400
    if len(content) > 2000:
        return jsonify({"error": "Comment too long (max 2000 chars)"}), 400

    comment.content = content
    comment.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"message": "Comment updated", "comment": comment.to_dict()}), 200


@comments_bp.route("/trades/<trade_id>/comments/<comment_id>", methods=["DELETE"])
@require_auth
def delete_comment(trade_id, comment_id):
    """Delete a comment (only the author can delete)."""
    user_id = get_jwt_identity()

    comment = Comment.query.filter_by(id=comment_id, trade_id=trade_id).first()
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    if comment.user_id != user_id:
        # Allow the trade owner to also delete comments
        trade = Trade.query.get(trade_id)
        if not trade or trade.trader_id != user_id:
            return jsonify({"error": "You can only delete your own comments"}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({"message": "Comment deleted"}), 200
