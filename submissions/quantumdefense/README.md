
# QuantumDefense – Intelligent Cybersecurity System

## Project Overview

QuantumDefense is a cybersecurity monitoring prototype designed to identify suspicious security events and unusual activity patterns.

It combines rule-based detection, machine learning, and database storage.

## Implemented Features

- Flask-based security dashboard
- Rule-based event detection
- Isolation Forest anomaly detection prototype
- Security event and alert storage
- ML analysis history
- SQLite development database
- IBM Db2 integration code and SQL schema

## Technology Stack

- Python
- Flask
- Scikit-learn
- Isolation Forest
- SQLite
- IBM Db2
- IBM Db2 Python Driver
- HTML and CSS

## Project Structure

```text
quantumdefense/
├── src/
│   ├── app.py
│   ├── analyzer.py
│   ├── database.py
│   ├── db2_manager.py
│   ├── detector.py
│   ├── storage.py
│   └── templates/
│       └── index.html
├── sql/
│   └── schema.sql
├── tests/
├── docs/
│   └── screenshots/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Installation

Create and activate a Python virtual environment.

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env`.

Keep the development database setting:

```env
DB_BACKEND=sqlite
```

Start the application:

```bash
python src/app.py
```

Open the application at:

```text
http://localhost:5000
```

## Machine Learning

The prototype uses the Isolation Forest algorithm to identify unusual patterns.

Current training and test data are synthetic. The model has not yet been validated against real network traffic.

## IBM Db2 Integration

The project includes:

- Db2 connection functions
- SQL table definitions
- Security event storage
- Security alert storage
- ML analysis result storage

A live Db2 connection requires valid database credentials and successful connection testing.

## Current Limitations

- Network events are simulated.
- ML metrics are illustrative.
- Detection rules are predefined.
- Quantum computing integration is not implemented yet.
- Quantum-resistant cryptography is not implemented yet.
- Blockchain integrity verification is not implemented yet.
- Live IBM Db2 integration is pending database access.

## Project Status

This is an ongoing educational cybersecurity prototype.


## Screenshots & Demo

The following screenshots demonstrate the QuantumDefense application.

### 1. Dashboard Overview

![Dashboard Overview](docs/screenshots/Screenshot%202026-10-31%20141205.png)

### 2. Security Event Detection

![Security Event Detection](docs/screenshots/Screenshot%202026-10-31%20141215.png)

### 3. Security Alerts

![Security Alerts](docs/screenshots/Screenshot%202026-10-31%20141222.png)

### 4. AI / ML Analysis

![AI ML Analysis](docs/screenshots/Screenshot%202026-10-31%20141228.png)

### 5. Anomaly Detection Results

![Anomaly Detection Results](docs/screenshots/Screenshot%202026-10-31%20141240.png)

### 6. Final Dashboard

![Final Dashboard](docs/screenshots/Screenshot%202026-10-31%20141248.png)

## Testing & Verification

Automated tests are written using pytest.

Run all tests:

```bash
python -m pytest -v
```

### Test Results

| Test Category | Passed |
|---|---:|
| Security Event Detection | 6 |
| AI Anomaly Detection | 4 |
| SQLite Database Operations | 4 |
| **Total** | **14/14** |

All 14 automated tests passed successfully in the development environment.

Note: These tests verify the application logic and SQLite storage. They do not verify a live IBM Db2 connection.