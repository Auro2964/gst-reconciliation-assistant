"""
Comprehensive End-to-End Test Suite for ClearRecon GST
Tests:
- Reconciliation & Matching Engine (engine.py)
- LLM Explanation & Draft Communication Layer (llm_helper.py)
- Status Tracker & Local SQLite Persistence (tracker.py)
- Multi-Client Portfolio Aggregator (multi_client.py)
- Multi-Sheet Excel CA Audit Exporter (exporter.py)
"""

import os
import unittest
import pandas as pd
import engine
import tracker
import llm_helper
import multi_client
import exporter

class TestGSTReconciliation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clean database to ensure test independence from mock data
        tracker.clear_db()
        cls.pr_df = pd.read_excel('purchase_register.xlsx')
        cls.g2b_df = pd.read_excel('gstr2b.xlsx')
        cls.result = engine.reconcile(cls.pr_df, cls.g2b_df, clean_match_tolerance=50.0)

    def test_01_matching_engine_accuracy(self):
        """Test exact matching and classification accuracy against ground truth."""
        summary = self.result['summary']
        self.assertEqual(summary['total_pr_invoices'], 34)
        self.assertEqual(summary['total_g2b_invoices'], 31)
        self.assertEqual(summary['matched_count'], 26)
        self.assertEqual(summary['match_rate_pct'], 76.5)
        self.assertEqual(summary['missing_in_portal_count'], 4)
        self.assertEqual(summary['amount_mismatch_count'], 4)
        self.assertEqual(summary['missing_in_books_count'], 1)
        self.assertEqual(summary['exception_count'], 9)
        self.assertAlmostEqual(summary['missing_in_portal_risk'], 49721.23, places=2)
        self.assertAlmostEqual(summary['amount_mismatch_risk'], 58669.60, places=2)
        self.assertAlmostEqual(summary['missing_in_books_risk'], 7560.00, places=2)
        self.assertAlmostEqual(summary['total_itc_at_risk'], 115950.83, places=2)

    def test_02_risk_ranking(self):
        """Test that exceptions are ranked strictly descending by Rupee Amount at Risk."""
        exceptions = self.result['exceptions']
        self.assertFalse(exceptions.empty)
        risk_amts = exceptions['risk_amount'].tolist()
        self.assertEqual(risk_amts, sorted(risk_amts, reverse=True))
        # Top risk should be Kumar Hardware Supplies or Chennai Steel Works (> ₹14,000)
        self.assertGreaterEqual(risk_amts[0], 14000.0)

    def test_03_conservative_fuzzy_matching(self):
        """Test conservative fuzzy matching: invoice numbers matched only if amounts agree."""
        # Check normalized match for INV1009 vs INV-1009
        matched = self.result['matched']
        inv_matches = matched[matched['pr_invoice_no'].str.contains('1009')]
        self.assertFalse(inv_matches.empty)
        # Check that INV-1002 and INV-9999 were NOT false matched despite both being Universal Traders
        inv_1002 = self.result['exceptions'][self.result['exceptions']['pr_invoice_no'] == 'INV-1002']
        self.assertEqual(len(inv_1002), 1)
        self.assertEqual(inv_1002.iloc[0]['category'], 'Missing in GSTR-2B (Supplier Not Filed)')

    def test_04_llm_explanations(self):
        """Test plain-English root cause explanation generation."""
        exceptions = self.result['exceptions']
        
        # Test Missing in 2B explanation
        row_missing_2b = exceptions[exceptions['category'].str.contains('Missing in GSTR-2B')].iloc[0].to_dict()
        exp_2b = llm_helper.explain_exception(row_missing_2b, client_name='Universal Polymers')
        self.assertIn('Section 16(2)(aa)', exp_2b['plain_english'])
        self.assertIn('DRC-01C', exp_2b['plain_english'])
        self.assertTrue(len(exp_2b['likely_causes']) >= 3)

        # Test Amount Mismatch explanation
        row_mismatch = exceptions[exceptions['category'] == 'Amount Mismatch'].iloc[0].to_dict()
        exp_mismatch = llm_helper.explain_exception(row_mismatch, client_name='Universal Polymers')
        self.assertIn('Taxable Value', exp_mismatch['plain_english'])
        self.assertIn('Credit Note', exp_mismatch['likely_causes'][0])

    def test_05_draft_communications(self):
        """Test ready-to-send email and WhatsApp drafting."""
        exceptions = self.result['exceptions']
        row = exceptions.iloc[0].to_dict()
        drafts = llm_helper.draft_communication(row, client_name='Universal Polymers')
        
        self.assertTrue(len(drafts['email_subject']) > 10)
        self.assertIn(str(row['pr_invoice_no'] if row['pr_invoice_no']!='—' else row['g2b_invoice_no']), drafts['email_body'])
        self.assertIn('*', drafts['whatsapp_text'])  # WhatsApp bold markdown
        self.assertTrue(drafts['whatsapp_url'].startswith('https://api.whatsapp.com/send?text='))

    def test_06_tracker_persistence(self):
        """Test SQLite status tracker synchronization and updates."""
        client_name = 'Test_Client_Recon'
        exceptions = self.result['exceptions']
        
        synced_df = tracker.sync_exceptions_to_db(client_name, exceptions)
        self.assertIn('exception_uid', synced_df.columns)
        first_uid = synced_df.iloc[0]['exception_uid']
        
        # Update status
        success = tracker.update_status(
            client_name, 
            first_uid, 
            'Sent for Follow-up', 
            assigned_to='Priya CA', 
            notes='Sent WhatsApp message to Accounts head Rohan'
        )
        self.assertTrue(success)
        
        # Verify persistence
        re_synced = tracker.sync_exceptions_to_db(client_name, exceptions)
        matching_row = re_synced[re_synced['exception_uid'] == first_uid].iloc[0]
        self.assertEqual(matching_row['status'], 'Sent for Follow-up')
        self.assertEqual(matching_row['assigned_to'], 'Priya CA')
        self.assertIn('Rohan', matching_row['notes'])

    def test_07_multi_client_portfolio(self):
        """Test firm-wide multi-client aggregation metrics with real persisted data."""
        # Also sync a second client to test multi-client aggregation
        tracker.sync_exceptions_to_db('Second_Client_Corp', self.result['exceptions'].head(2))
        
        port = multi_client.get_portfolio_metrics()
        self.assertGreaterEqual(port['client_count'], 2)
        self.assertGreater(port['open_exposure'], 0)
        self.assertFalse(port['top_exceptions'].empty)
        self.assertFalse(port['client_table'].empty)
        self.assertIn('Portfolio Status', port['client_table'].columns)

    def test_08_excel_export(self):
        """Test Excel CA audit pack export."""
        audit_bytes = exporter.generate_excel_audit_pack(self.result, client_name='Universal Polymers')
        self.assertGreater(len(audit_bytes), 5000)
        import io
        xl = pd.ExcelFile(io.BytesIO(audit_bytes), engine='openpyxl')
        self.assertIn('Executive Summary', xl.sheet_names)
        self.assertIn('Exceptions by Risk', xl.sheet_names)
        self.assertIn('Vendor Follow-up List', xl.sheet_names)
        self.assertIn('Matched Archive', xl.sheet_names)

    def test_09_severity_and_suggested_actions(self):
        """Verify severity levels (HIGH > 5000, MEDIUM 500-5000, LOW < 500) and suggested actions."""
        exceptions = self.result['exceptions']
        self.assertIn('severity', exceptions.columns)
        self.assertIn('suggested_action', exceptions.columns)
        
        for idx, row in exceptions.iterrows():
            risk = row['risk_amount']
            sev = row['severity']
            if risk > 5000:
                self.assertEqual(sev, 'HIGH')
            elif risk >= 500:
                self.assertEqual(sev, 'MEDIUM')
            else:
                self.assertEqual(sev, 'LOW')
            
            # Action should be a non-empty plain English string
            self.assertTrue(len(str(row['suggested_action']).strip()) > 10)

if __name__ == '__main__':
    unittest.main()
