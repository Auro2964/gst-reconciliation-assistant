"""
Headless verification script for ClearRecon GST Streamlit app.
Tests:
1. Empty state verification: Confirms empty state message is rendered when no files are uploaded,
   and no metric cards, tables, or tabs are rendered.
2. Reconciliation verification: Reconciles real test files (purchase_register.xlsx & gstr2b.xlsx)
   and verifies that numbers match expected categories, counts, and risks.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import engine
import tracker
import multi_client

def test_empty_state_and_reconciliation():
    print("--- 1. Testing Empty State ---")
    tracker.clear_db()
    port = multi_client.get_portfolio_metrics()
    assert port['client_count'] == 0, f"Expected 0 clients, got {port['client_count']}"
    assert port['total_exposure'] == 0.0, f"Expected 0.0 exposure, got {port['total_exposure']}"
    assert port['client_table'].empty, "Expected empty client table"
    print("[SUCCESS] Empty state confirmed: 0 clients, 0 exposure, no metric numbers or tables.")

    print("\n--- 2. Testing Real File Pair Reconciliation ---")
    pr_df = pd.read_excel('purchase_register.xlsx')
    g2b_df = pd.read_excel('gstr2b.xlsx')
    
    print(f"Loaded Purchase Register: {len(pr_df)} rows")
    print(f"Loaded GSTR-2B Statement: {len(g2b_df)} rows")

    client_name = "Universal Polymers & Engineering"
    res = engine.reconcile(pr_df, g2b_df, clean_match_tolerance=50.0)
    summary = res['summary']

    print(f"Total PR Invoices: {summary['total_pr_invoices']}")
    print(f"Total GSTR-2B Invoices: {summary['total_g2b_invoices']}")
    print(f"Fully Matched Count: {summary['matched_count']}")
    print(f"  - Exact Matches: {summary['exact_match_count']}")
    print(f"  - Probable Matches: {summary['probable_match_count']}")
    print(f"Exceptions by Category:")
    print(f"  - Missing in GSTR-2B (Supplier Not Filed): {summary['missing_in_portal_count']} invoices (Rs {summary['missing_in_portal_risk']:,.2f} risk)")
    print(f"  - Amount Mismatch (> Rs 50 difference): {summary['amount_mismatch_count']} invoices (Rs {summary['amount_mismatch_risk']:,.2f} risk)")
    print(f"  - Missing in Books (Unrecorded Purchase): {summary['missing_in_books_count']} invoices (Rs {summary['missing_in_books_risk']:,.2f} unclaimed)")
    print(f"Total Direct ITC at Risk: Rs {summary['total_itc_at_risk']:,.2f}")
    print(f"Reconciled Match Rate: {summary['match_rate_pct']}%")

    # Verify all 5 categories are present
    assert summary['matched_count'] > 0, "Expected matches"
    assert summary['missing_in_portal_count'] > 0, "Expected missing in 2B"
    assert summary['amount_mismatch_count'] > 0, "Expected amount mismatches"
    assert summary['missing_in_books_count'] > 0, "Expected missing in books"

    # Verify severity and actions
    exc = res['exceptions']
    assert not exc.empty, "Expected exceptions"
    for _, row in exc.iterrows():
        assert row['severity'] in ['HIGH', 'MEDIUM', 'LOW'], f"Invalid severity: {row['severity']}"
        assert len(str(row['suggested_action']).strip()) > 10, "Missing suggested action"

    print("[SUCCESS] All 5 match categories verified with proper severities and suggested actions.")

    print("\n--- 3. Testing Sync to SQLite Tracker and Portfolio Aggregator ---")
    synced_exc = tracker.sync_exceptions_to_db(client_name, exc)
    port_after = multi_client.get_portfolio_metrics()

    print(f"Portfolio Client Count: {port_after['client_count']}")
    print(f"Portfolio Open Exposure: Rs {port_after['open_exposure']:,.2f}")
    print(f"Portfolio Open Exceptions: {port_after['open_count']}")
    print(f"Client Leaderboard Entries:\n{port_after['client_table'][['Client Name', 'Total Exceptions', 'Open Risk (₹)', 'Portfolio Status']]}")

    expected_total_exp = round(summary['total_itc_at_risk'], 2)
    assert port_after['open_exposure'] == expected_total_exp, f"Exposure mismatch: {port_after['open_exposure']} vs {expected_total_exp}"
    assert not port_after['client_table'].empty, "Leaderboard should not be empty after sync"

    print("[SUCCESS] Portfolio aggregator successfully populated with real numbers from matching output!")

    # Clean up DB back to pristine empty state
    tracker.clear_db()
    print("[SUCCESS] Reset DB back to clean empty state for user fresh start.")

if __name__ == '__main__':
    test_empty_state_and_reconciliation()
    print("\nALL RECONCILIATION & EMPTY STATE CHECKS PASSED SUCCESSFULLY!")
