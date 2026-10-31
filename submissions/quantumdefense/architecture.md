
# QuantumDefense – System Architecture

## 1. Overview

QuantumDefense is an educational cybersecurity monitoring prototype.

It accepts simulated security events, analyses them using predefined rules and an Isolation Forest machine-learning model, and stores the results.

## 2. Architecture Components

### User Interface
- Flask web application
- HTML and CSS dashboard
- Security event submission form
- Security event and ML history

### Detection Layer
- Rule-based event detection
- Severity classification
- Input validation

### Machine Learning Layer
- Scikit-learn
- Isolation Forest
- Synthetic training data
- Anomaly score generation

### Database Layer
- SQLite development database
- IBM Db2 connection module
- Security event table
- Security alert table
- ML analysis results table

## 3. Data Flow

1. User submits a simulated security event.
2. Flask validates the input.
3. Rule-based detector analyses the event.
4. Isolation Forest analyses illustrative numerical metrics.
5. Security event and alert are stored.
6. ML analysis result is stored.
7. Dashboard displays the results and history.

## 4. Database Tables

| Table | Purpose |
|---|---|
| SECURITY_EVENTS | Security event records |
| SECURITY_ALERTS | Generated security alerts |
| ML_ANALYSIS_RESULTS | ML analysis history |
| SECURITY_AUDIT | Audit activity |

## 5. Current Implementation Limitations

- Network events are simulated.
- ML training data is synthetic.
- IBM Db2 live connection is pending credentials.
- Quantum computing integration is not implemented.
- Quantum-resistant cryptography is not implemented.
- Blockchain integrity verification is not implemented.

## 6. Future Enhancements

- Real network monitoring using authorised test data.
- ML training using suitable network datasets.
- IBM Db2 live database integration.
- Qiskit-based quantum computing experiments.
- Quantum-resistant cryptographic protection.
- Blockchain-based audit integrity verification.
