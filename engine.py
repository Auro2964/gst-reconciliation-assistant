"""
GST Reconciliation and Matching Engine
Pure functional matching engine that compares Purchase Register against GSTR-2B.
Adheres strictly to CA audit rules, Section 16(2)(aa) of CGST Act, and conservative matching logic.

Matching Logic:
1. Exact match: Same supplier GSTIN + same invoice number + tax/total amounts match within ₹50.
2. Probable match: Same GSTIN + invoice numbers match with minor difference (normalized, prefix/suffix/punctuation variations, or Levenshtein distance <= 1) + amounts match within ₹50.
3. Amount mismatch: Same GSTIN + same invoice number, but amounts differ by > ₹50.
4. Missing in 2B: In purchase register but not in GSTR-2B (vendor didn't file — ITC at risk).
5. Missing in PR: In GSTR-2B but not in purchase register (potential unclaimed ITC).

For every exception:
- Tax amount at risk (rupees)
- Severity: HIGH (> ₹5,000 at risk), MEDIUM (₹500–₹5,000), LOW (< ₹500)
- Suggested action in plain English
"""

import re
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
from rapidfuzz.distance import Levenshtein


def normalize_invoice_no(inv_val) -> str:
    """
    Normalizes invoice numbers by removing punctuation, spaces, and leading zeros.
    Example: 'INV-1009' -> 'INV1009', '001009' -> '1009', 'INV/2026/10' -> 'INV202610'.
    """
    if pd.isna(inv_val):
        return ""
    val_str = str(inv_val).strip().upper()
    cleaned = re.sub(r'[\s\-_/.\\]+', '', val_str)
    lstripped = cleaned.lstrip('0')
    return lstripped if lstripped else cleaned


def normalize_gstin(gstin_val) -> str:
    """Normalizes GSTIN string (trimmed and uppercase)."""
    if pd.isna(gstin_val):
        return ""
    return str(gstin_val).strip().upper()


def _amount_similarity(a: float, b: float) -> float:
    """Returns a ratio 0.0–1.0 indicating how similar two amounts are (1.0 = identical)."""
    a, b = abs(a), abs(b)
    if a == 0.0 and b == 0.0:
        return 1.0
    if max(a, b) == 0.0:
        return 0.0
    return min(a, b) / max(a, b)


def compute_severity(risk_amount: float) -> Tuple[str, str]:
    """
    Computes exception severity based on risk:
    HIGH: > ₹5,000
    MEDIUM: ₹500 – ₹5,000
    LOW: < ₹500
    Returns (severity_upper, risk_level_title).
    """
    if risk_amount > 5000:
        return "HIGH", "High"
    elif risk_amount >= 500:
        return "MEDIUM", "Medium"
    else:
        return "LOW", "Low"


def map_pr_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects and maps varied Purchase Register column names to standard internal names:
    - gstin, supplier_name, invoice_no, invoice_date, taxable_amt, tax_amt, total_amt
    """
    col_mapping = {}
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    
    # GSTIN mapping
    for candidate in ['supplier gstin', 'gstin', 'gstin of supplier', 'party gstin', 'vendor gstin']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'gstin'
            break
            
    # Supplier Name
    for candidate in ['supplier name', 'trade/legal name', 'party name', 'vendor name', 'name']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'supplier_name'
            break
            
    # Invoice Number
    for candidate in ['bill no', 'invoice no', 'invoice number', 'bill number', 'voucher no', 'doc no']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'invoice_no'
            break
            
    # Invoice Date
    for candidate in ['bill date', 'invoice date', 'date', 'voucher date']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'invoice_date'
            break
            
    # Taxable Amount
    for candidate in ['taxable amount', 'taxable value', 'taxable val', 'taxable']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'taxable_amt'
            break
            
    # Tax Amount
    for candidate in ['tax amount', 'total tax', 'gst amount', 'tax amt', 'tax', 'integrated tax']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'tax_amt'
            break
            
    # Total Bill Amount
    for candidate in ['bill amount', 'invoice value', 'total amount', 'invoice val', 'bill amt', 'total val']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'total_amt'
            break
            
    mapped_df = df.rename(columns=col_mapping).copy()
    
    # If tax_amt is missing, check for igst + cgst + sgst
    if 'tax_amt' not in mapped_df.columns:
        igst = pd.to_numeric(mapped_df.get('igst', 0.0), errors='coerce').fillna(0.0)
        cgst = pd.to_numeric(mapped_df.get('cgst', 0.0), errors='coerce').fillna(0.0)
        sgst = pd.to_numeric(mapped_df.get('sgst', 0.0), errors='coerce').fillna(0.0)
        mapped_df['tax_amt'] = igst + cgst + sgst

    # Ensure default columns exist if missing
    for col in ['gstin', 'supplier_name', 'invoice_no', 'invoice_date', 'taxable_amt', 'tax_amt', 'total_amt']:
        if col not in mapped_df.columns:
            mapped_df[col] = 0.0 if 'amt' in col else ''
            
    # Clean numeric columns
    for num_col in ['taxable_amt', 'tax_amt', 'total_amt']:
        mapped_df[num_col] = pd.to_numeric(
            mapped_df[num_col].astype(str).str.replace(',', '').str.strip(), 
            errors='coerce'
        ).fillna(0.0)
        
    return mapped_df


def map_gstr2b_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects and maps standard GSTR-2B portal columns to internal standard format.
    GSTR-2B typically separates IGST, CGST, SGST. We compute total tax = IGST + CGST + SGST + Cess.
    """
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    col_mapping = {}
    
    # GSTIN
    for candidate in ['gstin of supplier', 'supplier gstin', 'gstin']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'gstin'
            break
            
    # Supplier Name
    for candidate in ['trade/legal name', 'supplier name', 'trade name', 'legal name', 'party name']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'supplier_name'
            break
            
    # Invoice Number
    for candidate in ['invoice number', 'invoice no', 'bill no', 'document number']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'invoice_no'
            break
            
    # Invoice Date
    for candidate in ['invoice date', 'bill date', 'date']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'invoice_date'
            break
            
    # Taxable Value
    for candidate in ['taxable value', 'taxable amount', 'taxable']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'taxable_amt'
            break
            
    # Total Value
    for candidate in ['invoice value', 'bill amount', 'total amount']:
        if candidate in cols_lower:
            col_mapping[cols_lower[candidate]] = 'total_amt'
            break
            
    mapped_df = df.rename(columns=col_mapping).copy()
    
    # Check for individual taxes
    igst_col = cols_lower.get('integrated tax') or cols_lower.get('igst')
    cgst_col = cols_lower.get('central tax') or cols_lower.get('cgst')
    sgst_col = cols_lower.get('state/ut tax') or cols_lower.get('sgst')
    cess_col = cols_lower.get('cess')
    
    igst = pd.to_numeric(mapped_df[igst_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0) if igst_col else 0.0
    cgst = pd.to_numeric(mapped_df[cgst_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0) if cgst_col else 0.0
    sgst = pd.to_numeric(mapped_df[sgst_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0) if sgst_col else 0.0
    cess = pd.to_numeric(mapped_df[cess_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0) if cess_col else 0.0
    
    if 'tax_amt' not in mapped_df.columns or (mapped_df['tax_amt'] == 0).all():
        mapped_df['tax_amt'] = igst + cgst + sgst + cess
        
    mapped_df['igst'] = igst
    mapped_df['cgst'] = cgst
    mapped_df['sgst'] = sgst
    
    # Clean numeric columns
    for num_col in ['taxable_amt', 'tax_amt', 'total_amt']:
        mapped_df[num_col] = pd.to_numeric(mapped_df[num_col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)
        
    # Ensure default text columns exist
    for col in ['gstin', 'supplier_name', 'invoice_no', 'invoice_date']:
        if col not in mapped_df.columns:
            mapped_df[col] = ''
            
    return mapped_df


def reconcile(pr_df: pd.DataFrame, g2b_df: pd.DataFrame,
              clean_match_tolerance: float = 50.0,
              **kwargs) -> Dict[str, Any]:
    """
    Pure functional matching engine that compares Purchase Register against GSTR-2B.
    
    Matching categories:
    1. Exact Match: Same GSTIN + same invoice number + amounts within ₹50
    2. Probable Match: Same GSTIN + invoice numbers match with minor difference + amounts within ₹50
    3. Amount Mismatch: Same GSTIN + same invoice number, but amounts differ by > ₹50
    4. Missing in 2B: In purchase register but not in GSTR-2B (vendor didn't file — ITC at risk)
    5. Missing in PR: In GSTR-2B but not in purchase register (unclaimed ITC)
    """
    # Accommodate alias parameter if passed from UI
    if 'amount_tolerance' in kwargs and kwargs['amount_tolerance'] is not None:
        clean_match_tolerance = float(kwargs['amount_tolerance'])

    pr = map_pr_columns(pr_df)
    g2b = map_gstr2b_columns(g2b_df)

    # Add normalized keys
    pr['norm_gstin'] = pr['gstin'].apply(normalize_gstin)
    pr['norm_inv'] = pr['invoice_no'].apply(normalize_invoice_no)

    g2b['norm_gstin'] = g2b['gstin'].apply(normalize_gstin)
    g2b['norm_inv'] = g2b['invoice_no'].apply(normalize_invoice_no)

    matched_pr_indices = set()
    matched_g2b_indices = set()

    matched_records = []
    exception_records = []

    # ---- STAGE 1: Exact & Normalized Invoice Matching ----
    for pr_idx, pr_row in pr.iterrows():
        candidates = g2b[
            (g2b['norm_gstin'] == pr_row['norm_gstin']) &
            (g2b['norm_inv'] == pr_row['norm_inv']) &
            (~g2b.index.isin(matched_g2b_indices))
        ]
        if candidates.empty:
            continue

        pr_total = float(pr_row['total_amt'])

        # If multiple candidates, pick the one with closest total amount
        if len(candidates) > 1:
            diffs = candidates['total_amt'].apply(lambda x: abs(float(x) - pr_total))
            g2b_idx = diffs.idxmin()
        else:
            g2b_idx = candidates.index[0]

        g2b_row = g2b.loc[g2b_idx]
        matched_pr_indices.add(pr_idx)
        matched_g2b_indices.add(g2b_idx)

        g2b_total = float(g2b_row['total_amt'])
        total_diff = abs(pr_total - g2b_total)
        tax_diff = round(float(pr_row['tax_amt']) - float(g2b_row['tax_amt']), 2)
        taxable_diff = round(float(pr_row['taxable_amt']) - float(g2b_row['taxable_amt']), 2)

        supplier_name = pr_row['supplier_name'] or g2b_row['supplier_name']
        invoice_date = str(pr_row['invoice_date'] or g2b_row['invoice_date'])

        # Check whether raw invoice numbers were identical or normalized
        is_raw_exact = (str(pr_row['invoice_no']).strip().upper() == str(g2b_row['invoice_no']).strip().upper())
        match_label = 'Exact Match' if is_raw_exact else 'Probable Match (Normalized)'

        if total_diff <= clean_match_tolerance:
            # Clean match (within ₹50 tolerance)
            matched_records.append({
                'id': f"MATCH-{len(matched_records)+1}",
                'category': 'Fully Matched',
                'status': 'Resolved',
                'match_type': match_label,
                'supplier_name': supplier_name,
                'supplier_gstin': pr_row['gstin'],
                'pr_invoice_no': str(pr_row['invoice_no']),
                'g2b_invoice_no': str(g2b_row['invoice_no']),
                'invoice_date': invoice_date,
                'pr_taxable': float(pr_row['taxable_amt']),
                'g2b_taxable': float(g2b_row['taxable_amt']),
                'pr_tax': float(pr_row['tax_amt']),
                'g2b_tax': float(g2b_row['tax_amt']),
                'pr_total': pr_total,
                'g2b_total': g2b_total,
                'taxable_diff': taxable_diff,
                'tax_diff': tax_diff,
                'risk_amount': 0.0,
                'similarity_score': 100,
                'risk_level': 'None',
                'severity': 'LOW',
                'suggested_action': 'Matched within ₹50 tolerance. No action required.'
            })
        else:
            # Amount Mismatch (> ₹50 difference)
            risk_amt = round(total_diff, 2)
            sev_upper, sev_title = compute_severity(risk_amt)
            action = "Verify credit note for amount difference or request vendor to amend GSTR-1."
            explanation = (
                f"Invoice {pr_row['invoice_no']} from {supplier_name} matched between "
                f"books and GSTR-2B, but total amounts differ by ₹{total_diff:,.2f}. "
                f"Books total: ₹{pr_total:,.2f}, Portal total: ₹{g2b_total:,.2f}. "
                f"Tax variance: ₹{abs(tax_diff):,.2f}. Likely causes include credit note "
                f"adjustments, freight/packaging charges, or data entry errors."
            )
            exception_records.append({
                'id': f"EXC-{len(exception_records)+1}",
                'category': 'Amount Mismatch',
                'status': 'Open',
                'match_type': 'Amount Mismatch',
                'supplier_name': supplier_name,
                'supplier_gstin': pr_row['gstin'],
                'pr_invoice_no': str(pr_row['invoice_no']),
                'g2b_invoice_no': str(g2b_row['invoice_no']),
                'invoice_date': invoice_date,
                'pr_taxable': float(pr_row['taxable_amt']),
                'g2b_taxable': float(g2b_row['taxable_amt']),
                'pr_tax': float(pr_row['tax_amt']),
                'g2b_tax': float(g2b_row['tax_amt']),
                'pr_total': pr_total,
                'g2b_total': g2b_total,
                'taxable_diff': taxable_diff,
                'tax_diff': tax_diff,
                'risk_amount': risk_amt,
                'similarity_score': 100,
                'risk_level': sev_title,
                'severity': sev_upper,
                'suggested_action': action,
                'explanation': explanation
            })

    # ---- STAGE 2: Probable Match (Conservative Fuzzy Fallback) ----
    remaining_pr = pr[~pr.index.isin(matched_pr_indices)]

    for pr_idx, pr_row in remaining_pr.iterrows():
        cand_g2b = g2b[
            (g2b['norm_gstin'] == pr_row['norm_gstin']) &
            (~g2b.index.isin(matched_g2b_indices))
        ]

        best_idx = None
        best_total_diff = float('inf')
        pr_total = float(pr_row['total_amt'])

        for g_idx, g_row in cand_g2b.iterrows():
            edit_dist = Levenshtein.distance(pr_row['norm_inv'], g_row['norm_inv'])
            if edit_dist > 1:
                continue

            g_total = float(g_row['total_amt'])
            if _amount_similarity(pr_total, g_total) < 0.97:
                continue

            diff = abs(pr_total - g_total)
            if diff < best_total_diff:
                best_total_diff = diff
                best_idx = g_idx

        if best_idx is not None:
            g2b_row = g2b.loc[best_idx]
            matched_pr_indices.add(pr_idx)
            matched_g2b_indices.add(best_idx)

            g2b_total = float(g2b_row['total_amt'])
            total_diff = abs(pr_total - g2b_total)
            tax_diff = round(float(pr_row['tax_amt']) - float(g2b_row['tax_amt']), 2)
            taxable_diff = round(float(pr_row['taxable_amt']) - float(g2b_row['taxable_amt']), 2)

            edit_dist = Levenshtein.distance(pr_row['norm_inv'], g2b_row['norm_inv'])
            max_len = max(len(pr_row['norm_inv']), len(g2b_row['norm_inv']), 1)
            sim_score = round((1 - edit_dist / max_len) * 100)

            supplier_name = pr_row['supplier_name'] or g2b_row['supplier_name']
            invoice_date = str(pr_row['invoice_date'] or g2b_row['invoice_date'])

            if total_diff <= clean_match_tolerance:
                matched_records.append({
                    'id': f"MATCH-{len(matched_records)+1}",
                    'category': 'Probable Match',
                    'status': 'Resolved',
                    'match_type': f'Probable Match (Fuzzy distance {edit_dist})',
                    'supplier_name': supplier_name,
                    'supplier_gstin': pr_row['gstin'],
                    'pr_invoice_no': str(pr_row['invoice_no']),
                    'g2b_invoice_no': str(g2b_row['invoice_no']),
                    'invoice_date': invoice_date,
                    'pr_taxable': float(pr_row['taxable_amt']),
                    'g2b_taxable': float(g2b_row['taxable_amt']),
                    'pr_tax': float(pr_row['tax_amt']),
                    'g2b_tax': float(g2b_row['tax_amt']),
                    'pr_total': pr_total,
                    'g2b_total': g2b_total,
                    'taxable_diff': taxable_diff,
                    'tax_diff': tax_diff,
                    'risk_amount': 0.0,
                    'similarity_score': sim_score,
                    'risk_level': 'None',
                    'severity': 'LOW',
                    'suggested_action': 'Probable match accepted. Minor typographical difference resolved.'
                })
            else:
                risk_amt = round(total_diff, 2)
                sev_upper, sev_title = compute_severity(risk_amt)
                action = "Verify invoice number typo and check credit note for amount variance."
                explanation = (
                    f"Invoice {pr_row['invoice_no']} fuzzy-matched to portal invoice "
                    f"{g2b_row['invoice_no']} (edit distance {edit_dist}), but total "
                    f"amounts differ by ₹{total_diff:,.2f}. Books: ₹{pr_total:,.2f}, "
                    f"Portal: ₹{g2b_total:,.2f}. Tax variance: ₹{abs(tax_diff):,.2f}."
                )
                exception_records.append({
                    'id': f"EXC-{len(exception_records)+1}",
                    'category': 'Amount Mismatch',
                    'status': 'Open',
                    'match_type': f'Probable Match, Value Discrepancy (edit distance {edit_dist})',
                    'supplier_name': supplier_name,
                    'supplier_gstin': pr_row['gstin'],
                    'pr_invoice_no': str(pr_row['invoice_no']),
                    'g2b_invoice_no': str(g2b_row['invoice_no']),
                    'invoice_date': invoice_date,
                    'pr_taxable': float(pr_row['taxable_amt']),
                    'g2b_taxable': float(g2b_row['taxable_amt']),
                    'pr_tax': float(pr_row['tax_amt']),
                    'g2b_tax': float(g2b_row['tax_amt']),
                    'pr_total': pr_total,
                    'g2b_total': g2b_total,
                    'taxable_diff': taxable_diff,
                    'tax_diff': tax_diff,
                    'risk_amount': risk_amt,
                    'similarity_score': sim_score,
                    'risk_level': sev_title,
                    'severity': sev_upper,
                    'suggested_action': action,
                    'explanation': explanation
                })

    # ---- STAGE 3: Missing in GSTR-2B (Supplier Not Filed) ----
    unmatched_pr = pr[~pr.index.isin(matched_pr_indices)]
    for pr_idx, pr_row in unmatched_pr.iterrows():
        pr_total = float(pr_row['total_amt'])
        # Use actual tax from books (not estimated)
        risk_amt = round(float(pr_row['tax_amt']), 2)
        if risk_amt == 0.0:
            # Fallback estimate if tax_amt is zero
            risk_amt = round(pr_total * 18 / 118, 2)
        sev_upper, sev_title = compute_severity(risk_amt)
        action = "Contact vendor to file GSTR-1"
        explanation = (
            f"Invoice {pr_row['invoice_no']} from {pr_row['supplier_name']} "
            f"({pr_row['gstin']}) is recorded in the purchase register but not found "
            f"in GSTR-2B. Supplier has likely not filed their GSTR-1 for this period. "
            f"ITC of ₹{risk_amt:,.2f} cannot be claimed under Section 16(2)(aa) "
            f"until the supplier files."
        )
        exception_records.append({
            'id': f"EXC-{len(exception_records)+1}",
            'category': 'Missing in GSTR-2B (Supplier Not Filed)',
            'status': 'Open',
            'match_type': 'Missing in 2B',
            'supplier_name': pr_row['supplier_name'],
            'supplier_gstin': pr_row['gstin'],
            'pr_invoice_no': str(pr_row['invoice_no']),
            'g2b_invoice_no': '—',
            'invoice_date': str(pr_row['invoice_date']),
            'pr_taxable': float(pr_row['taxable_amt']),
            'g2b_taxable': 0.0,
            'pr_tax': float(pr_row['tax_amt']),
            'g2b_tax': 0.0,
            'pr_total': pr_total,
            'g2b_total': 0.0,
            'taxable_diff': float(pr_row['taxable_amt']),
            'tax_diff': float(pr_row['tax_amt']),
            'risk_amount': risk_amt,
            'similarity_score': 0,
            'risk_level': sev_title,
            'severity': sev_upper,
            'suggested_action': action,
            'explanation': explanation
        })

    # ---- STAGE 4: Missing in Books (Unrecorded Purchase) ----
    unmatched_g2b = g2b[~g2b.index.isin(matched_g2b_indices)]
    for g_idx, g_row in unmatched_g2b.iterrows():
        g_total = float(g_row['total_amt'])
        # Use actual tax from portal (not estimated)
        risk_amt = round(float(g_row['tax_amt']), 2)
        if risk_amt == 0.0:
            # Fallback estimate if tax_amt is zero
            risk_amt = round(g_total * 18 / 118, 2)
        sev_upper, sev_title = compute_severity(risk_amt)
        action = "Verify with internal procurement and book invoice in tally to claim eligible ITC."
        explanation = (
            f"Invoice {g_row['invoice_no']} from {g_row['supplier_name']} "
            f"({g_row['gstin']}) appears in GSTR-2B but is not recorded in the "
            f"client's purchase register. This may represent an unrecorded purchase "
            f"or a vendor filing error. Potential unclaimed ITC: ₹{risk_amt:,.2f}."
        )
        exception_records.append({
            'id': f"EXC-{len(exception_records)+1}",
            'category': 'Missing in Books (Unrecorded Purchase)',
            'status': 'Open',
            'match_type': 'Missing in PR',
            'supplier_name': g_row['supplier_name'],
            'supplier_gstin': g_row['gstin'],
            'pr_invoice_no': '—',
            'g2b_invoice_no': str(g_row['invoice_no']),
            'invoice_date': str(g_row['invoice_date']),
            'pr_taxable': 0.0,
            'g2b_taxable': float(g_row['taxable_amt']),
            'pr_tax': 0.0,
            'g2b_tax': float(g_row['tax_amt']),
            'pr_total': 0.0,
            'g2b_total': g_total,
            'taxable_diff': -float(g_row['taxable_amt']),
            'tax_diff': -float(g_row['tax_amt']),
            'risk_amount': risk_amt,
            'similarity_score': 0,
            'risk_level': sev_title,
            'severity': sev_upper,
            'suggested_action': action,
            'explanation': explanation
        })

    # Convert to DataFrames
    exceptions_df = pd.DataFrame(exception_records)
    matched_df = pd.DataFrame(matched_records)

    if not matched_df.empty:
        # Sort matched invoices by invoice date (most recent first)
        matched_df['dt_temp'] = pd.to_datetime(matched_df['invoice_date'], errors='coerce')
        matched_df = matched_df.sort_values(by=['dt_temp', 'id'], ascending=[False, True]).drop(columns=['dt_temp']).reset_index(drop=True)

    if not exceptions_df.empty:
        # Rank by Rupee amount at risk descending (highest risk first)
        exceptions_df = exceptions_df.sort_values(
            by='risk_amount', ascending=False
        ).reset_index(drop=True)
        # Re-index exception IDs deterministically from EXC-1 to EXC-N by risk ranking
        exceptions_df['id'] = [f"EXC-{i+1}" for i in range(len(exceptions_df))]

    # Compute Summary Statistics
    total_pr_tax = round(float(pr['tax_amt'].sum()), 2)
    total_g2b_tax = round(float(g2b['tax_amt'].sum()), 2)

    matched_tax = round(
        matched_df['pr_tax'].sum() if not matched_df.empty else 0.0, 2
    )

    missing_in_portal_df = (
        exceptions_df[exceptions_df['category'] == 'Missing in GSTR-2B (Supplier Not Filed)']
        if not exceptions_df.empty else pd.DataFrame()
    )
    amount_mismatch_df = (
        exceptions_df[exceptions_df['category'] == 'Amount Mismatch']
        if not exceptions_df.empty else pd.DataFrame()
    )
    missing_in_books_df = (
        exceptions_df[exceptions_df['category'] == 'Missing in Books (Unrecorded Purchase)']
        if not exceptions_df.empty else pd.DataFrame()
    )

    exact_matches_count = len(matched_df[matched_df['match_type'] == 'Exact Match']) if not matched_df.empty else 0
    probable_matches_count = len(matched_df[matched_df['match_type'].str.contains('Probable')]) if not matched_df.empty else 0

    portal_risk = round(
        missing_in_portal_df['risk_amount'].sum()
        if not missing_in_portal_df.empty else 0.0, 2
    )
    amount_mismatch_risk = round(
        amount_mismatch_df['risk_amount'].sum()
        if not amount_mismatch_df.empty else 0.0, 2
    )
    unclaimed_books_itc = round(
        missing_in_books_df['risk_amount'].sum()
        if not missing_in_books_df.empty else 0.0, 2
    )

    # Downstream Total: sum of all three category totals
    total_itc_at_risk = round(portal_risk + amount_mismatch_risk + unclaimed_books_itc, 2)
    match_rate = round(
        (len(matched_df) / len(pr) * 100) if len(pr) > 0 else 0.0, 1
    )

    summary = {
        'total_pr_invoices': len(pr),
        'total_g2b_invoices': len(g2b),
        'total_pr_tax': total_pr_tax,
        'total_g2b_tax': total_g2b_tax,
        'matched_count': len(matched_df),
        'exact_match_count': exact_matches_count,
        'probable_match_count': probable_matches_count,
        'matched_tax': matched_tax,
        'match_rate_pct': match_rate,
        'exception_count': len(exceptions_df),
        'missing_in_portal_count': len(missing_in_portal_df),
        'missing_in_portal_risk': portal_risk,
        'amount_mismatch_count': len(amount_mismatch_df),
        'amount_mismatch_risk': amount_mismatch_risk,
        'missing_in_books_count': len(missing_in_books_df),
        'missing_in_books_risk': unclaimed_books_itc,
        'total_itc_at_risk': total_itc_at_risk,
        'total_exposure': total_itc_at_risk
    }

    return {
        'summary': summary,
        'exceptions': exceptions_df,
        'matched': matched_df,
        'raw_pr': pr_df,
        'raw_g2b': g2b_df,
        'mapped_pr': pr,
        'mapped_g2b': g2b
    }
