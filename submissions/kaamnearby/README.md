# KaamNearby

> One-line pitch: KaamNearby is a local service marketplace that helps customers find nearby skilled workers such as electricians, plumbers, cleaners, and repair professionals with transparent booking and price negotiation.

---

## 1. Problem Statement

Local skilled workers often struggle to reach customers in nearby areas, especially when there is no trusted digital platform that connects them with people who need urgent on-demand help. Customers also face problems such as:

- difficulty finding trustworthy local workers quickly
- no clear visibility of service availability and pricing
- poor communication before booking
- uncertainty while negotiating prices with workers
- lack of a simple system to track booking requests and confirmations

This fragmentation makes everyday services slow, unreliable, and stressful for both customers and workers. KaamNearby solves this by creating a direct local connection between service seekers and skilled professionals.

---

## 2. Solution Overview

KaamNearby is a platform where customers can discover nearby workers based on their service needs, location, and availability. The system supports:

- nearby worker discovery by category and city/area
- service request posting and matching
- booking creation with basic status tracking
- price negotiation between customer and worker
- a simple dashboard for managing workers and customer requests

The project is designed to be lightweight, easy to deploy, and practical for local service marketplaces. It helps workers get more visible opportunities and helps customers find reliable help quickly in their neighborhood.

---

## 3. Db2 Integration Details

This project uses SQLite for local application storage during development and testing.

- Database used: SQLite
- Reason: lightweight local setup, fast prototyping, and simple deployment for a hackathon project
- Db2 note: IBM Db2 is not used in the current implementation, so the project does not claim Db2 integration yet
- If the project is later upgraded for enterprise deployment, the next phase could include IBM Db2 with `ibm_db` or SQLAlchemy-based integration for production-ready analytics and enterprise scale data handling

This ensures the project remains honest, reproducible, and valid for the hackathon submission requirements.

---

## 4. Tech Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Jinja2 templates

---

## 5. Setup Instructions

### Clone the repository

```bash
git clone <your-repository-url>
cd IBM_Db2_TechX_Project_Submission
```

### Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```

### Install dependencies

```bash
pip install flask
```

If the project includes a `requirements.txt`, then use:

```bash
pip install -r requirements.txt
```

---

## 6. Configuration

Create a `.env` file if required for secret configuration or app settings.

Example:

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///kaamnearby.db
```

If you are using SQLite directly, make sure the database file is created in the project root or configured with a valid absolute/relative path.

---

## 7. Run / Test Steps

### Run the application

```bash
python app.py
```

Or, if using Flask app factory:

```bash
flask run
```

### Test basic functionality

1. Open the app in the browser
2. Register or create a worker/customer profile
3. Search for nearby workers by service category or area
4. Create a booking request
5. Test price negotiation flow
6. Confirm the booking status updates correctly

### Example validation commands

```bash
python -m py_compile app.py
```

If there are unit tests:

```bash
pytest
```

---

## 8. Future Roadmap

The next phase of KaamNearby can include:

- online payments and secure checkout
- rating and review system for workers and customers
- real-time notifications for booking updates
- worker location tracking and estimated arrival time
- admin dashboard for bookings, pricing, and service analytics
- mobile app support for Android and iOS
- multilingual support for regional local communities
- AI-based smart matching of worker skills to service requests

---

## Team Members & Credits

| Name | GitHub Handle | Role |
|---|---|---|
| Ashfaq Khan | [@ashpaqkhan068-hub](https://github.com/ashpaqkhan068-hub) | Project lead & backend development |
| Team Member 2 | [@username](https://github.com/username) | Frontend / UI design |
| Team Member 3 | [@username](https://github.com/username) | Testing & documentation |

---

## Notes for Hackathon Submission

This README follows the expected project submission structure for readability, technical clarity, and evaluation readiness. The project is intentionally honest about its current database choice (SQLite) and clearly explains future scalability paths for IBM Db2 adoption.

