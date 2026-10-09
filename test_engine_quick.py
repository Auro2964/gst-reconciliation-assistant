import engine
import pandas as pd

pr = pd.read_excel('purchase_register.xlsx')
g2b = pd.read_excel('gstr2b.xlsx')
res = engine.reconcile(pr, g2b)
s = res['summary']

print('=== SUMMARY ===')
for k, v in s.items():
    print(f'  {k}: {v}')

print()
print('=== EXCEPTIONS ===')
exc = res['exceptions']
print(f'  Total exceptions: {len(exc)}')
if not exc.empty:
    for cat, grp in exc.groupby('category'):
        print(f'  {cat}: count={len(grp)}, risk={grp["risk_amount"].sum():.2f}')
    print()
    print('Exception details:')
    for _, r in exc.iterrows():
        print(f'  {r["id"]} | {r["category"]} | {r["supplier_name"]} | PR:{r["pr_invoice_no"]} / G2B:{r["g2b_invoice_no"]} | risk={r["risk_amount"]:.2f} | tax_diff={r["tax_diff"]:.2f}')

print()
print('=== MATCHED ===')
m = res['matched']
print(f'  Total matched: {len(m)}')
if not m.empty:
    for mt, g in m.groupby('match_type'):
        print(f'  {mt}: {len(g)}')
    print()
    for _, r in m.iterrows():
        print(f'  {r["id"]} | {r["match_type"]} | {r["supplier_name"]} | PR:{r["pr_invoice_no"]} / G2B:{r["g2b_invoice_no"]} | pr_tax={r["pr_tax"]:.2f} / g2b_tax={r["g2b_tax"]:.2f} | diff={r["tax_diff"]:.2f}')

print()
print('=== ITC AT RISK CALCULATION CHECK ===')
print(f'  total_itc_at_risk (from summary): {s["total_itc_at_risk"]:.2f}')
print(f'  missing_in_portal_risk: {s["missing_in_portal_risk"]:.2f}')
print(f'  amount_mismatch_risk: {s["amount_mismatch_risk"]:.2f}')
print(f'  missing_in_books_risk: {s["missing_in_books_risk"]:.2f}')
print(f'  Sum = portal + mismatch: {s["missing_in_portal_risk"] + s["amount_mismatch_risk"]:.2f}')
