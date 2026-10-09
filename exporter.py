"""
Excel Audit Pack Exporter for GST Reconciliation
Generates a multi-sheet, professional Excel workbook for CA client audit documentation:
- Executive Summary & Certification
- High-Risk Exceptions List
- Vendor Follow-up Communication Sheet
- Matched Invoices Archive
"""

import io
import pandas as pd

def generate_excel_audit_pack(reconcile_result: dict, client_name: str, firm_name: str = "Chartered Accountants") -> bytes:
    """
    Creates an in-memory formatted Excel workbook containing all reconciliation schedules.
    """
    output = io.BytesIO()
    
    summary = reconcile_result['summary']
    exceptions_df = reconcile_result['exceptions']
    matched_df = reconcile_result['matched']
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Summary Statement
        summary_rows = [
            {'Particulars': 'Client Name', 'Value': client_name},
            {'Particulars': 'Tax Period / Reconciliation Date', 'Value': 'Current Tax Period'},
            {'Particulars': 'Auditing Firm', 'Value': firm_name},
            {'Particulars': 'Total Invoices in Purchase Register (Books)', 'Value': summary.get('total_pr_invoices', 0)},
            {'Particulars': 'Total Invoices in GSTR-2B (Portal)', 'Value': summary.get('total_g2b_invoices', 0)},
            {'Particulars': 'Total Eligible ITC Claimed in Books (₹)', 'Value': summary.get('total_pr_tax', 0.0)},
            {'Particulars': 'Total ITC Available on Portal GSTR-2B (₹)', 'Value': summary.get('total_g2b_tax', 0.0)},
            {'Particulars': 'Fully Reconciled Invoices Count', 'Value': summary.get('matched_count', 0)},
            {'Particulars': 'Reconciliation Match Rate (%)', 'Value': f"{summary.get('match_rate_pct', 0.0)}%"},
            {'Particulars': 'Total Invoices with Exceptions', 'Value': summary.get('exception_count', 0)},
            {'Particulars': 'Missing in GSTR-2B (Supplier Unfiled) Count', 'Value': summary.get('missing_in_portal_count', 0)},
            {'Particulars': 'Missing in GSTR-2B ITC Loss Risk (₹)', 'Value': summary.get('missing_in_portal_risk', 0.0)},
            {'Particulars': 'Amount Mismatches Count', 'Value': summary.get('amount_mismatch_count', 0)},
            {'Particulars': 'Amount Mismatch Variance Exposure (₹)', 'Value': summary.get('amount_mismatch_risk', 0.0)},
            {'Particulars': 'Missing in Books (Unclaimed ITC Opportunity) Count', 'Value': summary.get('missing_in_books_count', 0)},
            {'Particulars': 'Missing in Books Unclaimed ITC Value (₹)', 'Value': summary.get('missing_in_books_risk', 0.0)},
            {'Particulars': 'TOTAL INPUT TAX CREDIT (ITC) AT RISK (₹)', 'Value': summary.get('total_itc_at_risk', 0.0)},
            {'Particulars': 'Statutory Notice Reference', 'Value': 'CGST Act Section 16(2)(aa) & Rule 36(4)'}
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Executive Summary', index=False)
        
        # Sheet 2: Exceptions Ranked by Rupee Risk
        if not exceptions_df.empty:
            export_exc = exceptions_df[[
                'id', 'category', 'risk_amount', 'risk_level', 'supplier_name', 'supplier_gstin',
                'pr_invoice_no', 'g2b_invoice_no', 'invoice_date', 'pr_taxable', 'g2b_taxable',
                'taxable_diff', 'pr_tax', 'g2b_tax', 'tax_diff', 'status'
            ]].copy()
            export_exc.columns = [
                'Exception ID', 'Discrepancy Category', 'Rupee Risk (₹)', 'Risk Level', 'Supplier Name', 'Supplier GSTIN',
                'Books Invoice No', 'Portal Invoice No', 'Invoice Date', 'Books Taxable (₹)', 'Portal Taxable (₹)',
                'Taxable Diff (₹)', 'Books Tax (₹)', 'Portal Tax (₹)', 'Tax Diff (₹)', 'Tracker Status'
            ]
            export_exc.to_excel(writer, sheet_name='Exceptions by Risk', index=False)
            
            # Sheet 3: Vendor Follow-Up List (Filter to Missing in 2B and Mismatches)
            follow_ups = export_exc[export_exc['Discrepancy Category'].isin([
                'Missing in GSTR-2B (Supplier Not Filed)', 'Amount Mismatch'
            ])].copy()
            if not follow_ups.empty:
                follow_ups.to_excel(writer, sheet_name='Vendor Follow-up List', index=False)
                
        # Sheet 4: Matched Records Archive
        if not matched_df.empty:
            export_matched = matched_df[[
                'id', 'match_type', 'supplier_name', 'supplier_gstin', 'pr_invoice_no',
                'g2b_invoice_no', 'invoice_date', 'pr_taxable', 'pr_tax', 'pr_total'
            ]].copy()
            export_matched.columns = [
                'Match ID', 'Match Method', 'Supplier Name', 'Supplier GSTIN', 'Books Inv No',
                'Portal Inv No', 'Invoice Date', 'Taxable Value (₹)', 'Tax Value (₹)', 'Invoice Total (₹)'
            ]
            export_matched.to_excel(writer, sheet_name='Matched Archive', index=False)
            
    output.seek(0)
    return output.getvalue()
