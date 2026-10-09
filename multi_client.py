"""
Multi-Client Dashboard and Portfolio Aggregation Engine
Aggregates reconciliation exceptions across all clients handled by the CA firm,
calculates firm-wide exposure, ranks clients by rupee risk, and highlights portfolio hotspots.
Data comes exclusively from real reconciliation results stored in the SQLite tracker.
"""

from typing import List, Dict, Any
import pandas as pd
import tracker


def get_portfolio_metrics() -> Dict[str, Any]:
    """Computes high-level aggregated metrics across all firm clients.
    Only includes clients with real reconciliation data in the tracker database."""
    tracker.init_db()
    conn = tracker.get_connection()
    cursor = conn.cursor()

    # Portfolio totals
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT client_name) as client_count,
            COUNT(*) as total_exceptions,
            SUM(risk_amount) as total_exposure,
            SUM(CASE WHEN status = 'Open' THEN risk_amount ELSE 0 END) as open_exposure,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN status = 'Sent for Follow-up' THEN 1 ELSE 0 END) as followup_count,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_count
        FROM exception_status
    """)
    res = cursor.fetchone()

    client_count = res[0] or 0

    if client_count == 0:
        conn.close()
        return {
            'client_count': 0,
            'total_exceptions': 0,
            'total_exposure': 0.0,
            'open_exposure': 0.0,
            'open_count': 0,
            'followup_count': 0,
            'resolved_count': 0,
            'resolution_rate': 0.0,
            'categories_breakdown': {},
            'top_exceptions': pd.DataFrame(),
            'client_table': pd.DataFrame()
        }

    total_exceptions = res[1] or 0
    total_exposure = round(res[2] or 0.0, 2)
    open_exposure = round(res[3] or 0.0, 2)
    open_count = res[4] or 0
    followup_count = res[5] or 0
    resolved_count = res[6] or 0

    resolution_rate = round(
        (resolved_count / total_exceptions * 100)
        if total_exceptions > 0 else 0.0, 1
    )

    # Category totals
    cursor.execute("""
        SELECT category, COUNT(*), SUM(risk_amount)
        FROM exception_status
        GROUP BY category
    """)
    cat_rows = cursor.fetchall()

    categories_breakdown = {}
    for cat, count, risk in cat_rows:
        categories_breakdown[cat] = {'count': count, 'risk': round(risk or 0.0, 2)}

    # Top 10 high-risk exceptions across all clients
    cursor.execute("""
        SELECT client_name, invoice_no, supplier_name, category, risk_amount, status, assigned_to
        FROM exception_status
        ORDER BY risk_amount DESC
        LIMIT 10
    """)
    top_exceptions = cursor.fetchall()

    top_exceptions_list = []
    for r in top_exceptions:
        top_exceptions_list.append({
            'client_name': r[0],
            'invoice_no': r[1],
            'supplier_name': r[2],
            'category': r[3],
            'risk_amount': round(r[4] or 0.0, 2),
            'status': r[5],
            'assigned_to': r[6]
        })

    # Client rankings
    cursor.execute("""
        SELECT 
            client_name,
            COUNT(*) as total_exc,
            SUM(CASE WHEN status = 'Open' THEN risk_amount ELSE 0 END) as open_risk,
            SUM(risk_amount) as total_risk,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_count,
            SUM(CASE WHEN status = 'Sent for Follow-up' THEN 1 ELSE 0 END) as followup_count,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_count
        FROM exception_status
        GROUP BY client_name
        ORDER BY open_risk DESC
    """)
    client_ranks = cursor.fetchall()

    conn.close()

    client_table = []
    for cr in client_ranks:
        tot = cr[1]
        res_cnt = cr[4]
        rate = round((res_cnt / tot * 100) if tot > 0 else 0.0, 1)
        open_risk_val = round(cr[2] or 0.0, 2)

        status_tag = (
            "Critical Risk" if open_risk_val >= 30000
            else ("Moderate" if open_risk_val >= 10000 else "Good Standing")
        )

        client_table.append({
            'Client Name': cr[0],
            'Total Exceptions': tot,
            'Open Risk (₹)': open_risk_val,
            'Total Exposure (₹)': round(cr[3] or 0.0, 2),
            'Open': cr[6],
            'Follow-up': cr[5],
            'Resolved': res_cnt,
            'Resolution %': f"{rate}%",
            'Portfolio Status': status_tag
        })

    return {
        'client_count': client_count,
        'total_exceptions': total_exceptions,
        'total_exposure': total_exposure,
        'open_exposure': open_exposure,
        'open_count': open_count,
        'followup_count': followup_count,
        'resolved_count': resolved_count,
        'resolution_rate': resolution_rate,
        'categories_breakdown': categories_breakdown,
        'top_exceptions': pd.DataFrame(top_exceptions_list),
        'client_table': pd.DataFrame(client_table)
    }
