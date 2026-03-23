"""
Export routes
- GET /api/pro-trader/reports/export-csv  - Export trades as CSV
- GET /api/pro-trader/reports/export-pdf  - Export monthly report as PDF
"""
import io
import csv
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, send_file, request
from flask_jwt_extended import get_jwt_identity

from app.middleware import require_pro_trader
from app.models.trade import Trade
from app.models.pro_trader_profile import ProTraderProfile
from app.models.profile import Profile

logger = logging.getLogger(__name__)
exports_bp = Blueprint("exports", __name__)


@exports_bp.route("/reports/export-csv", methods=["GET"])
@require_pro_trader
def export_trades_csv():
    """Export all trades as a CSV file."""
    user_id = get_jwt_identity()

    trades = Trade.query.filter_by(trader_id=user_id).order_by(Trade.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Symbol", "Direction", "Entry Price", "Stop Loss", "Target Price",
        "RRR", "Status", "Outcome", "Flag Count", "Created At", "Closed At", "Close Reason"
    ])

    for t in trades:
        writer.writerow([
            t.id,
            t.symbol,
            t.direction.upper(),
            float(t.entry_price),
            float(t.stop_loss_price),
            float(t.target_price),
            float(t.rrr),
            t.status,
            t.outcome or "",
            t.flag_count,
            t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            t.closed_at.strftime("%Y-%m-%d %H:%M:%S") if t.closed_at else "",
            t.close_reason or "",
        ])

    output.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"trades_export_{timestamp}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


@exports_bp.route("/reports/export-pdf", methods=["GET"])
@require_pro_trader
def export_monthly_report_pdf():
    """Export a monthly performance report as a PDF."""
    user_id = get_jwt_identity()

    month_str = request.args.get("month", "")
    now = datetime.now(timezone.utc)

    if month_str:
        try:
            report_month = datetime.strptime(month_str, "%Y-%m").replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify({"error": "Invalid month format. Use YYYY-MM"}), 400
    else:
        report_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if report_month.month == 12:
        month_end = report_month.replace(year=report_month.year + 1, month=1)
    else:
        month_end = report_month.replace(month=report_month.month + 1)

    trades = Trade.query.filter(
        Trade.trader_id == user_id,
        Trade.created_at >= report_month,
        Trade.created_at < month_end,
    ).order_by(Trade.created_at.desc()).all()

    pt_profile = ProTraderProfile.query.filter_by(user_id=user_id).first()
    profile = Profile.query.filter_by(user_id=user_id).first()

    trader_name = profile.display_name if profile else "Trader"
    total = len(trades)
    wins = sum(1 for t in trades if t.status == "target_hit")
    losses = sum(1 for t in trades if t.status == "sl_hit")
    accuracy = round((wins / (wins + losses)) * 100, 2) if (wins + losses) > 0 else 0.0

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=20, spaceAfter=12)
        elements.append(Paragraph("TradeWise Monthly Performance Report", title_style))
        elements.append(Paragraph(f"Trader: {trader_name}", styles["Normal"]))
        elements.append(Paragraph(f"Month: {report_month.strftime('%B %Y')}", styles["Normal"]))
        elements.append(Paragraph(f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
        elements.append(Spacer(1, 0.5 * cm))

        # Summary stats
        summary_data = [
            ["Metric", "Value"],
            ["Total Trades", str(total)],
            ["Wins", str(wins)],
            ["Losses", str(losses)],
            ["Accuracy", f"{accuracy}%"],
            ["Accuracy Score", f"{float(pt_profile.accuracy_score or 0):.2f}%"],
            ["Monthly Earnings", f"₹{float(pt_profile.total_earnings or 0):,.2f}"],
        ]
        summary_table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.5 * cm))

        # Trades table
        if trades:
            elements.append(Paragraph("Trade Details", styles["Heading2"]))
            trade_data = [["Symbol", "Direction", "Entry", "SL", "Target", "RRR", "Status", "Date"]]
            for t in trades:
                trade_data.append([
                    t.symbol,
                    t.direction.upper(),
                    f"{float(t.entry_price):.2f}",
                    f"{float(t.stop_loss_price):.2f}",
                    f"{float(t.target_price):.2f}",
                    f"{float(t.rrr):.2f}",
                    t.status.replace("_", " ").title(),
                    t.created_at.strftime("%d/%m/%Y") if t.created_at else "",
                ])
            trade_table = Table(trade_data, colWidths=[2.5 * cm, 2 * cm, 2.3 * cm, 2.3 * cm, 2.3 * cm, 1.8 * cm, 2.5 * cm, 2.5 * cm])
            trade_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(trade_table)

        doc.build(elements)
        buffer.seek(0)

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"monthly_report_{report_month.strftime('%Y_%m')}_{timestamp}.pdf"

        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except ImportError:
        logger.error("ReportLab not installed")
        return jsonify({"error": "PDF generation is not available (missing dependency)"}), 503
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return jsonify({"error": "Failed to generate PDF report"}), 500
