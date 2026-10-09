import pandas as pd
import engine
import tracker
import multi_client
import exporter

def verify_audit():
    # 1. Clean DB
    tracker.clear_db()

    # 2. Reconcile
    pr = pd.read_excel('purchase_register.xlsx')
    g2b = pd.read_excel('gstr2b.xlsx')
    res = engine.reconcile(pr, g2b)
    s = res['summary']

    print('=== GROUND TRUTH AUDIT CHECKS ===')
    assert s['matched_count'] == 26, f"Expected 26, got {s['matched_count']}"
    assert s['match_rate_pct'] == 76.5, f"Expected 76.5, got {s['match_rate_pct']}"
    assert s['missing_in_portal_count'] == 4, f"Expected 4, got {s['missing_in_portal_count']}"
    assert abs(s['missing_in_portal_risk'] - 49721.23) < 0.01, f"Expected 49721.23, got {s['missing_in_portal_risk']}"
    assert s['amount_mismatch_count'] == 4, f"Expected 4, got {s['amount_mismatch_count']}"
    assert abs(s['amount_mismatch_risk'] - 58669.60) < 0.01, f"Expected 58669.60, got {s['amount_mismatch_risk']}"
    assert s['missing_in_books_count'] == 1, f"Expected 1, got {s['missing_in_books_count']}"
    assert abs(s['missing_in_books_risk'] - 7560.00) < 0.01, f"Expected 7560.00, got {s['missing_in_books_risk']}"
    assert s['exception_count'] == 9, f"Expected 9, got {s['exception_count']}"
    assert abs(s['total_itc_at_risk'] - 115950.83) < 0.01, f"Expected 115950.83, got {s['total_itc_at_risk']}"
    print('1. All summary metrics match ground truth exactly!')

    # 3. Sorting checks
    matched = res['matched']
    dt_series = pd.to_datetime(matched['invoice_date'])
    assert dt_series.is_monotonic_decreasing, 'Matched table is not sorted by invoice_date descending!'
    print('2. Matched table is sorted by invoice_date descending (most recent first)!')

    exc = res['exceptions']
    risk_series = exc['risk_amount']
    assert risk_series.is_monotonic_decreasing, 'Exception table is not sorted by risk_amount descending!'
    print('3. Exceptions table is sorted by risk_amount descending (highest risk first)!')

    # 4. Sync to DB & Multi-Client
    tracker.sync_exceptions_to_db('Universal Polymers & Engineering', exc)
    pm = multi_client.get_portfolio_metrics()
    assert abs(pm['total_exposure'] - 115950.83) < 0.01
    assert abs(pm['open_exposure'] - 115950.83) < 0.01
    assert pm['total_exceptions'] == 9
    assert pm['open_count'] == 9
    assert pm['categories_breakdown']['Missing in GSTR-2B (Supplier Not Filed)']['count'] == 4
    assert abs(pm['categories_breakdown']['Missing in GSTR-2B (Supplier Not Filed)']['risk'] - 49721.23) < 0.01
    assert pm['categories_breakdown']['Amount Mismatch']['count'] == 4
    assert abs(pm['categories_breakdown']['Amount Mismatch']['risk'] - 58669.60) < 0.01
    assert pm['categories_breakdown']['Missing in Books (Unrecorded Purchase)']['count'] == 1
    assert abs(pm['categories_breakdown']['Missing in Books (Unrecorded Purchase)']['risk'] - 7560.00) < 0.01
    print('4. Multi-client portfolio metrics match ground truth exactly!')

    # 5. Export check
    audit_bytes = exporter.generate_excel_audit_pack(res, 'Universal Polymers & Engineering')
    assert len(audit_bytes) > 1000
    print('5. Audit pack export generates valid Excel binary data!')

    # 6. Clean DB back to empty state
    tracker.clear_db()
    print('6. DB reset cleanly back to empty state for fresh user run!')
    print('\nALL AUDIT VERIFICATIONS PASSED 100%!')

if __name__ == '__main__':
    verify_audit()
