"""
Lightweight Status Tracker for GST Exceptions
Stores tracking status, staff assignees, notes, and communication logs locally in SQLite.
Guarantees 100% data privacy (no cloud servers, entirely local to CA firm machine).
"""

import sqlite3
import datetime
from typing import Optional, List, Dict, Any
import pandas as pd

DB_PATH = "gst_tracker.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the local SQLite database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Exceptions tracking table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exception_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        exception_uid TEXT NOT NULL,
        category TEXT NOT NULL,
        supplier_name TEXT,
        supplier_gstin TEXT,
        invoice_no TEXT,
        invoice_date TEXT,
        risk_amount REAL DEFAULT 0.0,
        tax_diff REAL DEFAULT 0.0,
        taxable_diff REAL DEFAULT 0.0,
        status TEXT DEFAULT 'Open',
        assigned_to TEXT DEFAULT 'Unassigned',
        notes TEXT DEFAULT '',
        last_action_date TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(client_name, exception_uid)
    );
    """)
    
    # Client registry table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        client_id TEXT PRIMARY KEY,
        client_name TEXT NOT NULL,
        gstin TEXT,
        contact_person TEXT,
        contact_email TEXT,
        contact_phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()

def generate_uid(client_name: str, supplier_gstin: str, invoice_no: str, category: str) -> str:
    """Generates deterministic unique ID for an exception."""
    c_clean = str(client_name).strip().upper()
    g_clean = str(supplier_gstin).strip().upper()
    i_clean = str(invoice_no).strip().upper()
    cat_clean = str(category).strip().upper()
    return f"{c_clean}_{g_clean}_{i_clean}_{cat_clean}"

def sync_exceptions_to_db(client_name: str, exceptions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Syncs freshly reconciled exceptions with existing DB records.
    Preserves existing status, assignee, and notes if already present in DB.
    Returns the enriched DataFrame with active status, assignee, and notes.
    """
    if exceptions_df.empty:
        return exceptions_df
        
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    enriched_rows = []
    
    for idx, row in exceptions_df.iterrows():
        inv_no = row['pr_invoice_no'] if row['pr_invoice_no'] != '—' else row['g2b_invoice_no']
        uid = generate_uid(client_name, row['supplier_gstin'], inv_no, row['category'])
        
        # Check if already exists in DB
        cursor.execute("""
            SELECT status, assigned_to, notes, last_action_date, updated_at 
            FROM exception_status 
            WHERE client_name = ? AND exception_uid = ?
        """, (client_name, uid))
        existing = cursor.fetchone()
        
        row_dict = row.to_dict()
        row_dict['exception_uid'] = uid
        
        if existing:
            row_dict['status'] = existing[0]
            row_dict['assigned_to'] = existing[1] or 'Unassigned'
            row_dict['notes'] = existing[2] or ''
            row_dict['last_action_date'] = existing[3] or ''
            cursor.execute("""
                UPDATE exception_status 
                SET risk_amount = ?, tax_diff = ?, taxable_diff = ?
                WHERE client_name = ? AND exception_uid = ?
            """, (float(row['risk_amount']), float(row['tax_diff']), float(row['taxable_diff']), client_name, uid))
        else:
            # Insert new default record
            cursor.execute("""
                INSERT INTO exception_status 
                (client_name, exception_uid, category, supplier_name, supplier_gstin, 
                 invoice_no, invoice_date, risk_amount, tax_diff, taxable_diff, 
                 status, assigned_to, notes, last_action_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', 'Unassigned', '', ?)
            """, (
                client_name, uid, row['category'], row['supplier_name'], row['supplier_gstin'],
                inv_no, row['invoice_date'], float(row['risk_amount']), float(row['tax_diff']),
                float(row['taxable_diff']), datetime.date.today().isoformat()
            ))
            row_dict['status'] = 'Open'
            row_dict['assigned_to'] = 'Unassigned'
            row_dict['notes'] = ''
            row_dict['last_action_date'] = datetime.date.today().isoformat()
            
        enriched_rows.append(row_dict)
        
    conn.commit()
    conn.close()
    
    return pd.DataFrame(enriched_rows)

def update_status(client_name: str, exception_uid: str, new_status: str, 
                  assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
    """Updates the workflow status, assignee, and notes for an exception."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP", "last_action_date = ?"]
    params = [new_status, datetime.date.today().isoformat()]
    
    if assigned_to is not None:
        updates.append("assigned_to = ?")
        params.append(assigned_to)
        
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
        
    params.extend([client_name, exception_uid])
    
    query = f"UPDATE exception_status SET {', '.join(updates)} WHERE client_name = ? AND exception_uid = ?"
    cursor.execute(query, params)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_client_status_summary(client_name: str) -> Dict[str, Any]:
    """Gets status breakdown for a specific client."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT status, COUNT(*), SUM(risk_amount) 
        FROM exception_status 
        WHERE client_name = ?
        GROUP BY status
    """, (client_name,))
    rows = cursor.fetchall()
    conn.close()
    
    summary = {
        'Open': {'count': 0, 'risk': 0.0},
        'Sent for Follow-up': {'count': 0, 'risk': 0.0},
        'Resolved': {'count': 0, 'risk': 0.0},
        'Ignored': {'count': 0, 'risk': 0.0}
    }
    
    for status, count, risk in rows:
        if status in summary:
            summary[status] = {'count': count, 'risk': round(risk or 0.0, 2)}
            
    return summary

def get_all_clients_summary() -> List[Dict[str, Any]]:
    """Retrieves aggregated exception statistics across all clients in the database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            client_name,
            COUNT(*) as total_exceptions,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN status = 'Sent for Follow-up' THEN 1 ELSE 0 END) as followup_count,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_count,
            SUM(CASE WHEN status = 'Open' THEN risk_amount ELSE 0 END) as open_risk,
            SUM(risk_amount) as total_risk
        FROM exception_status
        GROUP BY client_name
        ORDER BY open_risk DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            'client_name': r[0],
            'total_exceptions': r[1],
            'open_count': r[2],
            'followup_count': r[3],
            'resolved_count': r[4],
            'open_risk': round(r[5] or 0.0, 2),
            'total_risk': round(r[6] or 0.0, 2),
            'resolution_rate': round((r[4] / r[1] * 100) if r[1] > 0 else 0.0, 1)
        })
    return result

def add_audit_log(client_name: str, exception_uid: str, log_text: str):
    """Appends an audit note with timestamp."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT notes FROM exception_status WHERE client_name = ? AND exception_uid = ?", (client_name, exception_uid))
    res = cursor.fetchone()
    current_notes = res[0] if res and res[0] else ""
    timestamp = datetime.datetime.now().strftime("%d-%b %H:%M")
    new_notes = f"[{timestamp}] {log_text}\n{current_notes}".strip()
    
    cursor.execute("""
        UPDATE exception_status 
        SET notes = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE client_name = ? AND exception_uid = ?
    """, (new_notes, client_name, exception_uid))
    conn.commit()
    conn.close()

def get_distinct_clients() -> List[str]:
    """Returns list of unique client names with records in tracker."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT client_name FROM exception_status ORDER BY client_name")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]

def clear_db():
    """Clears all tracking records from database."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exception_status")
    cursor.execute("DELETE FROM clients")
    conn.commit()
    conn.close()

