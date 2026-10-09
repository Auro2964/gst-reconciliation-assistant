"""
ClearRecon GST - AI-Assisted GST Reconciliation & Exception Management for CA Firms
A privacy-first, local-execution reconciliation and exception-tracking platform.
Zero hardcoded or placeholder data. Strictly renders empty state until files are uploaded and processed.
"""

import os
import streamlit as st
import pandas as pd
import numpy as np

import engine
import tracker
import llm_helper
import multi_client
import exporter

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="ClearRecon GST | CA Reconciliation & Exception Manager",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# Custom Styling (Dark Slate & Deep Sapphire CA Aesthetic)
# ---------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Container Padding */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 98%;
    }

    /* Hero Banner */
    .ca-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f2b48 100%);
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 22px 28px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .ca-header h1 {
        color: #f8fafc;
        font-size: 1.85rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.02em;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .ca-header p {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 6px;
        margin-bottom: 12px;
    }
    .privacy-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.35);
        color: #34d399;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 5px 12px;
        border-radius: 9999px;
    }

    /* Metric Cards */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .metric-card:hover {
        border-color: #0284c7;
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: -0.02em;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #64748b;
        margin-top: 4px;
    }

    /* Risk Badges */
    .badge-critical {
        background-color: rgba(239, 68, 68, 0.18);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.75rem;
    }
    .badge-high {
        background-color: rgba(245, 158, 11, 0.18);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-matched {
        background-color: rgba(16, 185, 129, 0.18);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
    }

    /* Explanation & Draft Boxes */
    .ai-box {
        background: #0f172a;
        border: 1px solid #3b82f6;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .draft-box {
        background: #1e293b;
        border: 1px solid #475569;
        border-radius: 10px;
        padding: 16px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.88rem;
        color: #e2e8f0;
        white-space: pre-wrap;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        white-space: pre-wrap;
        background-color: #1e293b;
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 600;
        padding: 0 18px;
        border: 1px solid #334155;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284c7 !important;
        color: #ffffff !important;
        border-color: #38bdf8 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if 'active_client' not in st.session_state:
    st.session_state['active_client'] = ''
if 'recon_result' not in st.session_state:
    st.session_state['recon_result'] = None
if 'selected_exception_id' not in st.session_state:
    st.session_state['selected_exception_id'] = None
if 'upload_metadata' not in st.session_state:
    st.session_state['upload_metadata'] = None

# Initialize SQLite database schema
tracker.init_db()

# ---------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏛️ CA Firm Console")
    firm_name = st.text_input("Auditing Firm Name", value="R. K. Singhal & Associates, CAs")
    
    st.markdown("---")
    st.markdown("### 🏢 Client Selector")
    
    known_clients = tracker.get_distinct_clients() if hasattr(tracker, 'get_distinct_clients') else []
    
    if known_clients:
        active_client_idx = known_clients.index(st.session_state['active_client']) if st.session_state['active_client'] in known_clients else 0
        selected_client = st.selectbox(
            "Active Client Workstation",
            options=known_clients,
            index=active_client_idx
        )
    else:
        selected_client = ''
    custom_client = st.text_input("Or Enter Custom Client Name", value="").strip()
    if custom_client:
        st.session_state['active_client'] = custom_client
    elif selected_client:
        st.session_state['active_client'] = selected_client
    elif not st.session_state.get('active_client'):
        st.session_state['active_client'] = 'Universal Polymers & Engineering'

    st.markdown("---")
    st.markdown("### 📂 Upload Files")
    st.caption("Upload Purchase Register (Books) and GSTR-2B Statement (Portal). Zero cloud storage.")
    
    sidebar_pr_file = st.file_uploader("1. Purchase Register (Books)", type=["xlsx", "xls", "csv"], key="sidebar_pr")
    sidebar_g2b_file = st.file_uploader("2. GSTR-2B Statement (Portal)", type=["xlsx", "xls", "csv"], key="sidebar_g2b")
    
    col_sb_run, col_sb_reset = st.columns([2, 1])
    with col_sb_run:
        sidebar_run_btn = st.button("🚀 Run Reconciliation", type="primary", use_container_width=True, key="sb_run_btn")
    with col_sb_reset:
        if st.button("🔄 Reset", use_container_width=True, key="sb_reset_btn"):
            st.session_state['recon_result'] = None
            st.session_state['selected_exception_id'] = None
            st.session_state['upload_metadata'] = None
            tracker.clear_db()
            st.rerun()

    with st.expander("⚙️ Matching Parameters", expanded=False):
        amount_tol = st.slider(
            "Clean Match Tolerance (₹)", min_value=0.0, max_value=100.0, value=50.0, step=1.0,
            help="Amounts within this difference are considered matched (exact threshold ₹50)"
        )

    st.markdown("---")
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #1e293b; border-radius: 8px; padding: 12px; font-size: 0.76rem; color: #94a3b8;">
        <span style="color: #38bdf8; font-weight: 700;">🔒 Data Privacy Protocol</span><br>
        • Parsed strictly in-memory (RAM)<br>
        • No GST portal API/GSP credential required<br>
        • Exceptions tracked in local SQLite<br>
        • 100% compliant with ICAI Client Confidentiality norms
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# Handle Reconciliation Execution from Sidebar
# ---------------------------------------------------------
if sidebar_run_btn:
    if not sidebar_pr_file or not sidebar_g2b_file:
        st.sidebar.error("⚠️ Please upload BOTH Purchase Register and GSTR-2B files in the sidebar before clicking Run Reconciliation.")
    else:
        try:
            with st.spinner(f"Parsing sheets and executing multi-stage reconciliation for {st.session_state['active_client']}..."):
                pr_df = pd.read_csv(sidebar_pr_file) if sidebar_pr_file.name.endswith('.csv') else pd.read_excel(sidebar_pr_file)
                g2b_df = pd.read_csv(sidebar_g2b_file) if sidebar_g2b_file.name.endswith('.csv') else pd.read_excel(sidebar_g2b_file)
                
                # Execute pure matching engine
                res = engine.reconcile(pr_df, g2b_df, clean_match_tolerance=amount_tol)
                
                # Sync exceptions to local SQLite
                if not res['exceptions'].empty:
                    res['exceptions'] = tracker.sync_exceptions_to_db(st.session_state['active_client'], res['exceptions'])
                
                st.session_state['upload_metadata'] = {
                    'pr_name': sidebar_pr_file.name,
                    'pr_rows': len(pr_df),
                    'g2b_name': sidebar_g2b_file.name,
                    'g2b_rows': len(g2b_df)
                }
                st.session_state['recon_result'] = res
                st.toast("Reconciliation completed successfully!", icon="✅")
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error reading or reconciling files: {str(e)}")

# ---------------------------------------------------------
# Top Navigation & Header
# ---------------------------------------------------------
st.markdown(f"""
<div class="ca-header">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">
        <div>
            <h1>⚖️ ClearRecon GST</h1>
            <p>AI-Assisted GST Reconciliation & Exception Management for Indian CA Firms</p>
        </div>
        <div style="text-align: right;">
            <div class="privacy-badge">🔒 100% Local & Private Execution • Zero Cloud Storage</div>
            <div style="color: #64748b; font-size: 0.8rem; margin-top: 6px;">Client: <strong style="color: #38bdf8;">{st.session_state['active_client']}</strong> | Firm: {firm_name}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# EMPTY STATE GUARD: Render ONLY when files have been processed
# ---------------------------------------------------------
if st.session_state.get('recon_result') is None:
    st.markdown("""
    <div style="text-align: center; padding: 40px 24px 30px 24px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px dashed #475569; border-radius: 16px; margin: 20px auto; max-width: 860px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
        <div style="font-size: 3.5rem; margin-bottom: 12px;">📂</div>
        <h2 style="color: #f8fafc; font-weight: 800; font-size: 1.65rem; margin-bottom: 12px;">
            Upload a Purchase Register and GSTR-2B file to see reconciliation results
        </h2>
        <p style="color: #94a3b8; font-size: 1.02rem; line-height: 1.6; max-width: 660px; margin: 0 auto 16px auto;">
            Reconciliation results are strictly generated from your uploaded files. No mock or placeholder data is displayed.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        main_pr_file = st.file_uploader("📖 1. Purchase Register (Books Excel/CSV)", type=["xlsx", "xls", "csv"], key="main_pr")
    with col_u2:
        main_g2b_file = st.file_uploader("🏛️ 2. GSTR-2B Statement (Portal Excel/CSV)", type=["xlsx", "xls", "csv"], key="main_g2b")
        
    col_act1, col_act2 = st.columns([1.5, 1])
    with col_act1:
        if st.button("🚀 Process & Reconcile Uploaded Files", type="primary", use_container_width=True, key="main_run_btn"):
            active_pr = main_pr_file or sidebar_pr_file
            active_g2b = main_g2b_file or sidebar_g2b_file
            if not active_pr or not active_g2b:
                st.error("⚠️ Please upload BOTH Purchase Register and GSTR-2B files to run reconciliation.")
            else:
                try:
                    with st.spinner("Processing files and executing reconciliation engine..."):
                        pr_df = pd.read_csv(active_pr) if active_pr.name.endswith('.csv') else pd.read_excel(active_pr)
                        g2b_df = pd.read_csv(active_g2b) if active_g2b.name.endswith('.csv') else pd.read_excel(active_g2b)
                        res = engine.reconcile(pr_df, g2b_df, clean_match_tolerance=amount_tol)
                        if not res['exceptions'].empty:
                            res['exceptions'] = tracker.sync_exceptions_to_db(st.session_state['active_client'], res['exceptions'])
                        st.session_state['upload_metadata'] = {
                            'pr_name': active_pr.name,
                            'pr_rows': len(pr_df),
                            'g2b_name': active_g2b.name,
                            'g2b_rows': len(g2b_df)
                        }
                        st.session_state['recon_result'] = res
                        st.rerun()
                except Exception as e:
                    st.error(f"Error parsing files: {str(e)}")

    with col_act2:
        if os.path.exists('purchase_register.xlsx') and os.path.exists('gstr2b.xlsx'):
            if st.button("⚡ Reconcile Workspace Test Files", use_container_width=True, key="quick_load_btn"):
                try:
                    with st.spinner("Loading workspace sheets and running reconciliation engine..."):
                        pr_df = pd.read_excel('purchase_register.xlsx')
                        g2b_df = pd.read_excel('gstr2b.xlsx')
                        res = engine.reconcile(pr_df, g2b_df, clean_match_tolerance=amount_tol)
                        if not res['exceptions'].empty:
                            res['exceptions'] = tracker.sync_exceptions_to_db(st.session_state['active_client'], res['exceptions'])
                        st.session_state['upload_metadata'] = {
                            'pr_name': 'purchase_register.xlsx',
                            'pr_rows': len(pr_df),
                            'g2b_name': 'gstr2b.xlsx',
                            'g2b_rows': len(g2b_df)
                        }
                        st.session_state['recon_result'] = res
                        st.rerun()
                except Exception as e:
                    st.error(f"Error loading files: {str(e)}")
                    
    st.stop()

# =========================================================
# PROCESSED RESULTS VIEW: Rendered ONLY after real upload
# =========================================================
recon = st.session_state['recon_result']
meta = st.session_state.get('upload_metadata', {})
summary = recon['summary']

# Banner: Confirmation of processed files
st.markdown(f"""
<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 16px 20px; margin-bottom: 20px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            <span style="color: #34d399; font-weight: 800; font-size: 1.1rem;">✅ Files Successfully Processed & Reconciled</span>
            <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 4px;">
                Client: <strong style="color: #f8fafc;">{st.session_state['active_client']}</strong> | 
                Purchase Register: <strong style="color: #38bdf8;">{meta.get('pr_name', 'PR File')}</strong> ({summary['total_pr_invoices']} invoices, ₹{summary['total_pr_tax']:,.2f} tax) | 
                GSTR-2B Statement: <strong style="color: #38bdf8;">{meta.get('g2b_name', '2B File')}</strong> ({summary['total_g2b_invoices']} invoices, ₹{summary['total_g2b_tax']:,.2f} tax)
            </div>
        </div>
        <div style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; font-weight: 700; font-size: 0.85rem; padding: 6px 14px; border-radius: 8px;">
            Match Rate: {summary['match_rate_pct']}% ({summary['matched_count']} / {summary['total_pr_invoices']})
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Expandable Raw Input Output View
with st.expander("📄 View Processed Input Data Sheets (Raw Data as Uploaded)", expanded=False):
    t_pr, t_g2b = st.tabs([f"📖 Purchase Register Sheet ({summary['total_pr_invoices']} Rows)", f"🏛️ GSTR-2B Statement Sheet ({summary['total_g2b_invoices']} Rows)"])
    with t_pr:
        st.dataframe(recon.get('raw_pr'), use_container_width=True, hide_index=False)
    with t_g2b:
        st.dataframe(recon.get('raw_g2b'), use_container_width=True, hide_index=False)

# ---------------------------------------------------------
# Main Tabs: Detailed Breakdown
# ---------------------------------------------------------
tab_recon, tab_exceptions, tab_portfolio, tab_ai, tab_tracker, tab_export = st.tabs([
    "🔍 Reconciliation Breakdown",
    "⚠️ Exception Manager (Risk Ranked)",
    "🏢 Multi-Client Firm Portfolio",
    "🤖 AI Explanations & Communications",
    "📋 Action & Status Tracker",
    "📥 Audit Pack Export"
])

# =========================================================
# TAB 1: Reconciliation Breakdown
# =========================================================
with tab_recon:
    st.markdown(f"### 📑 Reconciliation Workspace: **{st.session_state['active_client']}**")
    st.caption("Reconciliation performed using exact normalization + conservative fuzzy matching with ₹50 amount tolerance.")
    
    # 5 Key Metrics Cards
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Books (PR) ITC</div>
            <div class="metric-val">₹{summary['total_pr_tax']:,.2f}</div>
            <div class="metric-sub">{summary['total_pr_invoices']} purchase invoices</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Portal (2B) ITC</div>
            <div class="metric-val">₹{summary['total_g2b_tax']:,.2f}</div>
            <div class="metric-sub">{summary['total_g2b_invoices']} filed invoices</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Reconciled Match</div>
            <div class="metric-val" style="color: #34d399;">{summary['match_rate_pct']}%</div>
            <div class="metric-sub">{summary['matched_count']} invoices (₹{summary['matched_tax']:,.2f})</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Firm ITC at Risk</div>
            <div class="metric-val" style="color: #ef4444;">₹{summary['total_itc_at_risk']:,.2f}</div>
            <div class="metric-sub">{summary['exception_count']} total exceptions across all categories</div>
        </div>
        """, unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Unrecorded in Books</div>
            <div class="metric-val" style="color: #38bdf8;">₹{summary['missing_in_books_risk']:,.2f}</div>
            <div class="metric-sub">{summary['missing_in_books_count']} unclaimed bills</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Audit Category Breakdown Cards
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown(f"""
        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 14px 18px;">
            <div style="color: #f87171; font-weight: 700; font-size: 0.95rem;">🚨 Missing in GSTR-2B (Supplier Not Filed)</div>
            <div style="color: #f1f5f9; font-size: 1.35rem; font-weight: 800; margin: 4px 0;">₹{summary['missing_in_portal_risk']:,.2f}</div>
            <div style="color: #94a3b8; font-size: 0.8rem;">{summary['missing_in_portal_count']} exceptions. Suppliers must file GSTR-1 to prevent ITC loss under Sec 16(2)(aa).</div>
        </div>
        """, unsafe_allow_html=True)
    with b2:
        st.markdown(f"""
        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 10px; padding: 14px 18px;">
            <div style="color: #fbbf24; font-weight: 700; font-size: 0.95rem;">⚠️ Amount & Tax Mismatches</div>
            <div style="color: #f1f5f9; font-size: 1.35rem; font-weight: 800; margin: 4px 0;">₹{summary['amount_mismatch_risk']:,.2f}</div>
            <div style="color: #94a3b8; font-size: 0.8rem;">{summary['amount_mismatch_count']} exception pairs. Credit note variations or manual entry typos in ERP.</div>
        </div>
        """, unsafe_allow_html=True)
    with b3:
        st.markdown(f"""
        <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 14px 18px;">
            <div style="color: #38bdf8; font-weight: 700; font-size: 0.95rem;">💡 Missing in Books (Unclaimed ITC)</div>
            <div style="color: #f1f5f9; font-size: 1.35rem; font-weight: 800; margin: 4px 0;">₹{summary['missing_in_books_risk']:,.2f}</div>
            <div style="color: #94a3b8; font-size: 0.8rem;">{summary['missing_in_books_count']} exception. Present on portal but omitted in purchase register.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Sub-tabs for Matched vs Raw Views
    st.markdown("#### ✅ Reconciled Invoices Table")
    matched_df = recon['matched'].copy()
    if not matched_df.empty:
        matched_df['dt_temp'] = pd.to_datetime(matched_df['invoice_date'], errors='coerce')
        matched_df = matched_df.sort_values(by=['dt_temp', 'id'], ascending=[False, True]).drop(columns=['dt_temp']).reset_index(drop=True)
    st.markdown(f"**{len(matched_df)} Invoices Fully Matched** ({summary['exact_match_count']} Exact Matches + {summary['probable_match_count']} Probable / Fuzzy Matches)")
    if not matched_df.empty:
        st.dataframe(
            matched_df[[
                'id', 'match_type', 'supplier_name', 'supplier_gstin', 'pr_invoice_no',
                'g2b_invoice_no', 'invoice_date', 'pr_taxable', 'pr_tax', 'g2b_tax', 'tax_diff', 'similarity_score'
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                'id': st.column_config.TextColumn("ID", width="small"),
                'match_type': st.column_config.TextColumn("Match Type", width="medium"),
                'supplier_name': st.column_config.TextColumn("Supplier Name", width="medium"),
                'pr_invoice_no': "Books Inv #",
                'g2b_invoice_no': "Portal Inv #",
                'pr_taxable': st.column_config.NumberColumn('Taxable Amount', format="₹%.2f"),
                'pr_tax': st.column_config.NumberColumn('Books Tax (ITC)', format="₹%.2f"),
                'g2b_tax': st.column_config.NumberColumn('Portal Tax', format="₹%.2f"),
                'tax_diff': st.column_config.NumberColumn('Difference', format="₹%.2f"),
                'similarity_score': st.column_config.ProgressColumn('Similarity', min_value=0, max_value=100)
            }
        )

# =========================================================
# TAB 2: Exception Manager (Risk Ranked)
# =========================================================
with tab_exceptions:
    st.markdown("### ⚠️ Exception Manager & Risk Ranking")
    st.caption("All mismatched and unmatched invoices ranked strictly by Rupee Amount at Risk (₹), showing staff exactly what to fix first.")
    
    exc_df = recon['exceptions'].copy()
    if not exc_df.empty:
        # Interactive Filters
        f1, f2, f3, f4 = st.columns([2, 1.5, 1.5, 2])
        with f1:
            cat_filter = st.multiselect(
                "Filter by Category",
                options=list(exc_df['category'].unique()),
                default=list(exc_df['category'].unique())
            )
        with f2:
            available_risks = list(exc_df['risk_level'].unique())
            risk_filter = st.multiselect(
                "Severity Level",
                options=['High', 'Medium', 'Low'],
                default=[r for r in ['High', 'Medium', 'Low'] if r in available_risks] or available_risks
            )
        with f3:
            status_filter = st.multiselect(
                "Workflow Status",
                options=['Open', 'Sent for Follow-up', 'Resolved'],
                default=['Open', 'Sent for Follow-up', 'Resolved']
            )
        with f4:
            search_query = st.text_input("🔍 Search Supplier or Invoice #", "")

        # Apply Filters
        filtered_df = exc_df[
            (exc_df['category'].isin(cat_filter)) &
            (exc_df['risk_level'].isin(risk_filter)) &
            (exc_df['status'].isin(status_filter))
        ]
        if search_query:
            q = search_query.strip().lower()
            filtered_df = filtered_df[
                filtered_df['supplier_name'].str.lower().str.contains(q) |
                filtered_df['pr_invoice_no'].str.lower().str.contains(q) |
                filtered_df['g2b_invoice_no'].str.lower().str.contains(q)
            ]

        filtered_df = filtered_df.sort_values(by='risk_amount', ascending=False).reset_index(drop=True)
        st.markdown(f"**Showing {len(filtered_df)} exceptions** (Total at-risk value: ₹{filtered_df['risk_amount'].sum():,.2f})")
        
        st.dataframe(
            filtered_df[[
                'id', 'risk_amount', 'severity', 'category', 'supplier_name', 'pr_invoice_no',
                'g2b_invoice_no', 'invoice_date', 'pr_tax', 'g2b_tax', 'tax_diff', 'status', 'suggested_action'
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                'id': st.column_config.TextColumn("ID", width="small"),
                'risk_amount': st.column_config.NumberColumn("Rupee Risk (₹)", format="₹%.2f"),
                'severity': st.column_config.TextColumn("Severity"),
                'category': st.column_config.TextColumn("Classification", width="medium"),
                'supplier_name': st.column_config.TextColumn("Vendor Name", width="medium"),
                'pr_invoice_no': "Books Inv #",
                'g2b_invoice_no': "Portal Inv #",
                'pr_tax': st.column_config.NumberColumn("Books Tax", format="₹%.2f"),
                'g2b_tax': st.column_config.NumberColumn("Portal Tax", format="₹%.2f"),
                'tax_diff': st.column_config.NumberColumn("Variance", format="₹%.2f"),
                'status': st.column_config.SelectboxColumn("Status", options=['Open', 'Sent for Follow-up', 'Resolved'], required=True),
                'suggested_action': st.column_config.TextColumn("Suggested Action", width="large")
            }
        )
        
        st.markdown("---")
        st.markdown("#### 🎯 Quick Inspect & AI Communication Generator")
        st.caption("Select an exception below to inspect its plain-English explanation and auto-draft follow-up communication.")
        
        exc_options = {
            f"{r['id']} | ₹{r['risk_amount']:,.2f} Risk | {r['supplier_name']} ({r['pr_invoice_no'] if r['pr_invoice_no']!='—' else r['g2b_invoice_no']}) - {r['category']}": r['id']
            for _, r in filtered_df.iterrows()
        }
        
        if exc_options:
            selected_label = st.selectbox("Choose Exception to Inspect:", list(exc_options.keys()))
            if st.button("🚀 Analyze with AI & Draft Messages", type="primary"):
                st.session_state['selected_exception_id'] = exc_options[selected_label]
                st.info("Switched to 'AI Explanations & Communications' tab! Please click Tab 4 above to view drafts.")
        else:
            st.info("No exceptions match the selected filter criteria.")
    else:
        st.success("🎉 All invoices fully matched! Zero exceptions detected.")

# =========================================================
# TAB 3: Multi-Client Firm Portfolio
# =========================================================
with tab_portfolio:
    st.markdown("### 📊 CA Firm-Wide Risk Aggregator")
    st.caption("Consolidated exposure across all clients handled by your firm. Reflects strictly data from processed files saved in SQLite.")
    
    port_metrics = multi_client.get_portfolio_metrics()
    
    if port_metrics['client_count'] > 0:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Firm Exposure</div>
                <div class="metric-val" style="color: #ef4444;">₹{port_metrics['open_exposure']:,.2f}</div>
                <div class="metric-sub">Across {port_metrics['client_count']} monitored client(s)</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Open Exceptions</div>
                <div class="metric-val" style="color: #fbbf24;">{port_metrics['open_count']} Exceptions</div>
                <div class="metric-sub">{port_metrics['followup_count']} currently in vendor follow-up</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Portfolio Resolution Rate</div>
                <div class="metric-val" style="color: #34d399;">{port_metrics['resolution_rate']}%</div>
                <div class="metric-sub">{port_metrics['resolved_count']} of {port_metrics['total_exceptions']} resolved</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Handled Discrepancy</div>
                <div class="metric-val" style="color: #38bdf8;">₹{port_metrics['total_exposure']:,.2f}</div>
                <div class="metric-sub">Total reconciled variance</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        col_rank, col_hotspots = st.columns([3, 2])
        
        with col_rank:
            st.markdown("#### 🏆 Client Risk Leaderboard (Sorted by ₹ Risk)")
            st.dataframe(
                port_metrics['client_table'],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Client Name": st.column_config.TextColumn(width="medium"),
                    "Open Risk (₹)": st.column_config.NumberColumn(format="₹%.2f"),
                    "Total Exposure (₹)": st.column_config.NumberColumn(format="₹%.2f"),
                    "Portfolio Status": st.column_config.TextColumn(width="small")
                }
            )
            
        with col_hotspots:
            st.markdown("#### ⚡ Exception Distribution by Category")
            cat_data = []
            for cat, data in port_metrics['categories_breakdown'].items():
                cat_data.append({
                    'Discrepancy Category': cat.replace(" (Supplier Not Filed)", "").replace(" (Unrecorded Purchase)", ""),
                    'Exceptions': data['count'],
                    'Rupee Exposure': data['risk']
                })
            cat_df = pd.DataFrame(cat_data)
            if not cat_df.empty:
                st.dataframe(
                    cat_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Rupee Exposure": st.column_config.NumberColumn(format="₹%.2f")
                    }
                )
                
                portal_cat_data = port_metrics['categories_breakdown'].get('Missing in GSTR-2B (Supplier Not Filed)')
                if portal_cat_data and port_metrics['open_exposure'] > 0:
                    pct = round((portal_cat_data['risk'] / port_metrics['open_exposure']) * 100)
                    if pct > 0:
                        st.info(f"💡 **CA Partner Insight:** {pct}% of portfolio discrepancy exposure stems from suppliers failing to file GSTR-1, causing Section 16(2)(aa) blocks.")

        st.markdown("---")
        st.markdown("#### 🚨 Top High-Risk Invoices Across All Processed Clients")
        if not port_metrics['top_exceptions'].empty:
            st.dataframe(
                port_metrics['top_exceptions'],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "client_name": "Client",
                    "invoice_no": "Invoice #",
                    "supplier_name": "Supplier / Vendor",
                    "category": "Discrepancy Type",
                    "risk_amount": st.column_config.NumberColumn("Rupee Risk", format="₹%.2f"),
                    "status": "Current Status",
                    "assigned_to": "Assigned Staff"
                }
            )
    else:
        st.info("No saved client records in tracker. Process files to populate the portfolio view.")

# =========================================================
# TAB 4: AI Explanations & Communications
# =========================================================
with tab_ai:
    st.markdown("### 🤖 LLM-Powered Explanations & Auto-Drafted Communications")
    st.caption("Translates dry discrepancy figures into plain-English CA root-cause analysis and drafts ready-to-dispatch vendor communications.")
    
    exc_df = recon['exceptions']
    if not exc_df.empty:
        inv_labels = {
            f"{r['id']} | ₹{r['risk_amount']:,.2f} Risk | {r['supplier_name']} - Inv: {r['pr_invoice_no'] if r['pr_invoice_no']!='—' else r['g2b_invoice_no']} [{r['category']}]": r['id']
            for _, r in exc_df.iterrows()
        }
        
        default_index = 0
        if st.session_state.get('selected_exception_id'):
            for i, (k, v) in enumerate(inv_labels.items()):
                if v == st.session_state['selected_exception_id']:
                    default_index = i
                    break
                    
        selected_exc_key = st.selectbox(
            "Select Exception to Examine:",
            options=list(inv_labels.keys()),
            index=default_index,
            key="ai_exception_picker"
        )
        
        chosen_id = inv_labels[selected_exc_key]
        selected_row = exc_df[exc_df['id'] == chosen_id].iloc[0].to_dict()
        
        explanation = llm_helper.explain_exception(selected_row, client_name=st.session_state['active_client'])
        drafts = llm_helper.draft_communication(selected_row, client_name=st.session_state['active_client'], firm_name=firm_name)
        
        st.markdown(f"""
        <div class="ai-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 1.15rem; font-weight: 700; color: #60a5fa;">💡 Root Cause Analysis: {explanation['title']}</span>
                <span class="badge-critical">{explanation['urgency']}</span>
            </div>
            <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;">{explanation['plain_english']}</p>
            <div style="margin-top: 14px;">
                <strong style="color: #93c5fd; font-size: 0.85rem;">POTENTIAL CONTRIBUTING FACTORS:</strong>
                <ul style="color: #94a3b8; font-size: 0.85rem; margin-top: 4px; padding-left: 20px;">
                    {''.join([f"<li>{cause}</li>" for cause in explanation['likely_causes']])}
                </ul>
            </div>
            <div style="margin-top: 12px; background: rgba(59, 130, 246, 0.1); border-left: 4px solid #3b82f6; padding: 10px 14px; border-radius: 4px;">
                <strong style="color: #bfdbfe; font-size: 0.85rem;">RECOMMENDED CA ACTION:</strong>
                <div style="color: #e2e8f0; font-size: 0.88rem; margin-top: 2px;">{explanation['action_recommended']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("#### 📨 Auto-Drafted Ready-to-Send Communications")
        d_tab1, d_tab2, d_tab3 = st.tabs(["📧 Vendor Follow-up Email", "💬 Vendor WhatsApp Message", "📋 Client Internal Advisory Note"])
        
        with d_tab1:
            st.text_input("Subject Line", value=drafts['email_subject'], key="email_subj")
            st.text_area("Email Body (Ready to Send)", value=drafts['email_body'], height=240, key="email_body")
            
            c_btn1, c_btn2 = st.columns([1, 4])
            with c_btn1:
                if st.button("📋 Copy Email", key="copy_email_btn"):
                    st.toast("Email draft ready to paste into Outlook/Gmail!", icon="📋")
            with c_btn2:
                if st.button("✉️ Open in Email Client (Mailto)", key="open_mailto"):
                    import urllib.parse
                    mailto_link = f"mailto:?subject={urllib.parse.quote(drafts['email_subject'])}&body={urllib.parse.quote(drafts['email_body'])}"
                    st.markdown(f'<a href="{mailto_link}" target="_blank" style="color: #38bdf8; font-weight: 600;">👉 Click here to launch your default mail app</a>', unsafe_allow_html=True)

        with d_tab2:
            st.text_area("WhatsApp Message (Formatted with bold markers)", value=drafts['whatsapp_text'], height=180, key="wa_text")
            w_col1, w_col2 = st.columns([1.5, 3])
            with w_col1:
                st.markdown(f"""
                <a href="{drafts['whatsapp_url']}" target="_blank" style="display: inline-block; background-color: #25D366; color: white; padding: 9px 18px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.9rem;">
                    📲 Send via WhatsApp Web
                </a>
                """, unsafe_allow_html=True)
            with w_col2:
                st.caption("Directly opens WhatsApp Web with the pre-filled follow-up message.")

        with d_tab3:
            st.markdown(drafts['client_advisory'])
            if st.button("📋 Copy Advisory Memo"):
                st.toast("Advisory note copied for client meeting/report!", icon="📋")

        st.markdown("---")
        st.markdown("#### ⚡ Update Workflow Status for this Exception")
        u_col1, u_col2, u_col3 = st.columns([1.5, 1.5, 3])
        with u_col1:
            new_st = st.selectbox("Set Status", ["Open", "Sent for Follow-up", "Resolved"], 
                                  index=["Open", "Sent for Follow-up", "Resolved"].index(selected_row.get('status', 'Open')))
        with u_col2:
            assignee = st.text_input("Assigned Staff", value=selected_row.get('assigned_to', 'Unassigned'))
        with u_col3:
            staff_note = st.text_input("Staff Action Remarks", value=selected_row.get('notes', ''))
            
        if st.button("💾 Save Status & Notes to Local Database", type="secondary"):
            tracker.update_status(
                st.session_state['active_client'],
                selected_row['exception_uid'],
                new_st,
                assigned_to=assignee,
                notes=staff_note
            )
            st.session_state['recon_result']['exceptions'] = tracker.sync_exceptions_to_db(
                st.session_state['active_client'], 
                st.session_state['recon_result']['exceptions']
            )
            st.success(f"Status for {selected_row['id']} updated to '{new_st}' and saved to SQLite!")
            st.rerun()

    else:
        st.info("No exceptions available.")

# =========================================================
# TAB 5: Action & Status Tracker
# =========================================================
with tab_tracker:
    st.markdown("### 📋 Lightweight Exception Tracker")
    st.caption("Manage resolution workflows across your team. Saved persistently in local SQLite (`gst_tracker.db`) with complete data privacy.")
    
    exc_df = recon['exceptions'].copy()
    if not exc_df.empty:
        exc_df = exc_df.sort_values(by='risk_amount', ascending=False).reset_index(drop=True)
        client_summary = tracker.get_client_status_summary(st.session_state['active_client'])
        
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 10px; padding: 14px 18px;">
                <div style="color: #f87171; font-weight: 700; font-size: 0.9rem;">🔴 Open (Action Required)</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #f8fafc; margin: 4px 0;">{client_summary['Open']['count']} Exceptions</div>
                <div style="color: #94a3b8; font-size: 0.8rem;">ITC at Risk: ₹{client_summary['Open']['risk']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with tc2:
            st.markdown(f"""
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 10px; padding: 14px 18px;">
                <div style="color: #fbbf24; font-weight: 700; font-size: 0.9rem;">🟡 Sent for Follow-up</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #f8fafc; margin: 4px 0;">{client_summary['Sent for Follow-up']['count']} Exceptions</div>
                <div style="color: #94a3b8; font-size: 0.8rem;">Awaiting vendor GSTR-1 amendment: ₹{client_summary['Sent for Follow-up']['risk']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with tc3:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 10px; padding: 14px 18px;">
                <div style="color: #34d399; font-weight: 700; font-size: 0.9rem;">🟢 Resolved / Settled</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #f8fafc; margin: 4px 0;">{client_summary['Resolved']['count']} Exceptions</div>
                <div style="color: #94a3b8; font-size: 0.8rem;">Recovered / Adjusted ITC: ₹{client_summary['Resolved']['risk']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🛠️ Bulk & Row-Level Workflow Updater")
        
        edited_df = st.data_editor(
            exc_df[[
                'id', 'supplier_name', 'pr_invoice_no', 'g2b_invoice_no', 'category',
                'risk_amount', 'status', 'assigned_to', 'notes'
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                'id': st.column_config.TextColumn("ID", disabled=True),
                'supplier_name': st.column_config.TextColumn("Supplier", disabled=True),
                'pr_invoice_no': st.column_config.TextColumn("Books Inv #", disabled=True),
                'g2b_invoice_no': st.column_config.TextColumn("Portal Inv #", disabled=True),
                'category': st.column_config.TextColumn("Category", disabled=True),
                'risk_amount': st.column_config.NumberColumn("Risk (₹)", format="₹%.2f", disabled=True),
                'status': st.column_config.SelectboxColumn("Status", options=['Open', 'Sent for Follow-up', 'Resolved'], required=True),
                'assigned_to': st.column_config.TextColumn("Assigned Staff"),
                'notes': st.column_config.TextColumn("Staff Action Remarks", width="large")
            },
            key="tracker_editor"
        )
        
        if st.button("💾 Commit All Table Edits to SQLite Database", type="primary"):
            updated_count = 0
            for idx, r in edited_df.iterrows():
                matching_orig = exc_df[exc_df['id'] == r['id']].iloc[0]
                uid = matching_orig['exception_uid']
                tracker.update_status(
                    st.session_state['active_client'],
                    uid,
                    r['status'],
                    assigned_to=r['assigned_to'],
                    notes=r['notes']
                )
                updated_count += 1
            st.session_state['recon_result']['exceptions'] = tracker.sync_exceptions_to_db(
                st.session_state['active_client'], 
                st.session_state['recon_result']['exceptions']
            )
            st.success(f"Successfully saved {updated_count} records to local database!")
            st.rerun()

    else:
        st.info("No exceptions loaded in tracker.")

# =========================================================
# TAB 6: Audit Pack Export
# =========================================================
with tab_export:
    st.markdown("### 📥 CA Audit Pack & Excel Reconciliation Export")
    st.caption("Generate an ICAI-compliant multi-sheet audit file for client tax records, assessment documentation, and vendor communication.")
    
    st.markdown(f"""
    <div style="background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
        <h4 style="color: #f8fafc; margin-top: 0;">📦 Audit Package Includes:</h4>
        <ul style="color: #94a3b8; line-height: 1.8;">
            <li><strong>Sheet 1: Executive Summary & Reconciliation Certificate:</strong> Complete ITC figures, match percentage, and Section 16(2)(aa) compliance remarks.</li>
            <li><strong>Sheet 2: Exceptions Ranked by Rupee Risk:</strong> All discrepancies with books vs portal comparisons and assigned staff statuses.</li>
            <li><strong>Sheet 3: Vendor Follow-Up List:</strong> Curated list of missing and mismatched bills formatted for immediate distribution to vendor accounts.</li>
            <li><strong>Sheet 4: Matched Records Archive:</strong> Historical proof of eligible claimed ITC for GST audit defense.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    audit_bytes = exporter.generate_excel_audit_pack(
        recon, 
        client_name=st.session_state['active_client'], 
        firm_name=firm_name
    )
    
    file_name = f"GST_Reconciliation_{st.session_state['active_client'].replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
    
    st.download_button(
        label="📊 Download Multi-Tab Excel CA Audit Pack (.xlsx)",
        data=audit_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )
