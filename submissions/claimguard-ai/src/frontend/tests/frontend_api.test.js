/**
 * ClaimGuard AI - Frontend API & System Integration Test Suite
 * Executed via Node.js native test runner (node --test)
 * Tests live frontend API contract against the running backend.
 */

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';

const API_BASE = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

describe('Frontend API Integration & System Contract', () => {
  let authToken = null;
  let testClaimId = null;

  test('01. Health Check Endpoint returns IBM Db2 and system status', async () => {
    const res = await fetch(`${API_BASE}/health`);
    assert.equal(res.status, 200, 'Health endpoint should return HTTP 200');
    const data = await res.json();
    assert.equal(data.app_name, 'ClaimGuard AI');
    assert.equal(data.version, '1.0.0');
    assert.ok(data.database, 'Database health section must be present');
    assert.equal(data.database.database, 'IBM Db2');
    assert.match(data.database.driver, /ibm_db 3\.3\.0/, 'Driver must be ibm_db 3.3.0');
    assert.equal(typeof data.database.connected, 'boolean', 'Reports true connection status honestly');
  });

  test('02. Authentication Endpoint issues JWT for authorized examiner', async () => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: 'examiner',
        password: 'examiner123'
      })
    });
    assert.equal(res.status, 200, 'Login should succeed with valid credentials');
    const data = await res.json();
    assert.ok(data.access_token, 'Response must include JWT access token');
    assert.equal(data.token_type, 'bearer');
    assert.equal(data.user.role, 'REVIEWER');
    authToken = data.access_token;
  });

  test('03. Dashboard Statistics returns aggregated metrics', async () => {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.ok(typeof data.total_claims === 'number', 'total_claims must be a number');
    assert.ok(typeof data.pending_claims === 'number', 'pending_claims must be a number');
    assert.ok(typeof data.total_claimed_amount === 'number', 'total_claimed_amount must be numeric');
    assert.ok('active_alerts' in data, 'active_alerts must be present');
  });

  test('04. Claims Listing returns structured claims array', async () => {
    const res = await fetch(`${API_BASE}/claims`);
    assert.equal(res.status, 200);
    const claims = await res.json();
    assert.ok(Array.isArray(claims), 'Claims must be returned as an array');
    if (claims.length > 0) {
      const first = claims[0];
      assert.ok(first.claim_id, 'Each claim must have claim_id');
      assert.ok(first.policy_id, 'Each claim must reference policy_id');
      assert.ok(typeof first.risk_score === 'number', 'risk_score must be numeric');
    }
  });

  test('05. Claim Submission validates and persists new claim', async () => {
    const res = await fetch(`${API_BASE}/claims`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        policy_id: 'POL-1001',
        customer_id: 'CUST-001',
        incident_date: '2026-03-01',
        admission_date: '2026-03-02',
        discharge_date: '2026-03-05',
        claim_amount: 11500.0,
        hospital_name: 'Max Healthcare',
        hospital_invoice_number: 'INV-FRONTEND-101',
        diagnosis_code: 'J18.9',
        diagnosis_description: 'Pneumonia unspecified'
      })
    });
    assert.equal(res.status, 201, 'Claim creation should return HTTP 201');
    const created = await res.json();
    assert.ok(created.claim_id, 'Created claim must return generated claim_id');
    assert.equal(created.status, 'PENDING');
    testClaimId = created.claim_id;
  });

  test('06. Agentic Verification triggers 5-agent LangGraph orchestrator', async () => {
    assert.ok(testClaimId, 'testClaimId must exist from previous step');
    const res = await fetch(`${API_BASE}/verification/${testClaimId}`, {
      method: 'POST'
    });
    assert.equal(res.status, 200, 'Verification trigger must return HTTP 200');
    const result = await res.json();
    assert.equal(result.status, 'success');
    assert.equal(result.completed, true, 'LangGraph execution must complete');
    assert.ok(result.decision_output, 'Decision Agent output must be present');
    assert.ok(['APPROVE', 'INVESTIGATE', 'REJECT'].includes(result.decision_output.recommendation));
    assert.ok(typeof result.decision_output.risk_score === 'number');
  });

  test('07. AI Verification Report returns transparent explainability trail', async () => {
    assert.ok(testClaimId, 'testClaimId must exist');
    const res = await fetch(`${API_BASE}/reports/${testClaimId}`);
    assert.equal(res.status, 200);
    const report = await res.json();
    assert.ok(report.customer, 'Customer details must be included');
    assert.ok(report.policy, 'Policy limits must be included');
    assert.ok(report.risk_assessment, 'Risk assessment must be included');
    assert.ok(Array.isArray(report.risk_assessment.reasons), 'Reasons must be an array');
  });

  test('08. Fraud Alerts Endpoint retrieves security alerts', async () => {
    const res = await fetch(`${API_BASE}/fraud/alerts`);
    assert.equal(res.status, 200);
    const alerts = await res.json();
    assert.ok(Array.isArray(alerts), 'Alerts must be an array');
    if (alerts.length > 0) {
      assert.ok(alerts[0].alert_type, 'Alert must have alert_type');
      assert.ok(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(alerts[0].severity));
    }
  });

  test('09. Human Examiner Adjudication updates claim decision', async () => {
    assert.ok(testClaimId, 'testClaimId must exist');
    assert.ok(authToken, 'authToken must be available');
    const res = await fetch(`${API_BASE}/claims/${testClaimId}/decision`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        status: 'APPROVED',
        approved_amount: 11500.0,
        decision_notes: 'Verified against medical records. Approved via Frontend Integration Suite.'
      })
    });
    assert.equal(res.status, 200, 'Decision update should return HTTP 200');
    const updated = await res.json();
    assert.equal(updated.status, 'APPROVED');
    assert.equal(updated.approved_amount, 11500.0);
  });

  test('10. Error Handling returns structured JSON for non-existent routes', async () => {
    const res = await fetch(`${API_BASE}/claims/NON_EXISTENT_ID_9999`);
    assert.equal(res.status, 404, 'Non-existent claim should return HTTP 404');
    const errorData = await res.json();
    assert.ok(errorData.detail, 'Error response must contain detail message');
  });
});
