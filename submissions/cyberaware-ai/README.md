
# CyberAware AI
### An Intelligent Cybersecurity Awareness and Education Platform

## 1. Project Overview

CyberAware AI is a web-based cybersecurity awareness and education platform designed to help people recognize online scams, phishing messages, fraudulent calls, fake links, and other digital threats.

The platform makes cybersecurity knowledge simple and accessible to students, young people, parents, small business owners, and mobile money users.

## 2. Problem Statement

Many people use mobile money, social media, and online services without understanding common cybersecurity threats.

They may receive fraudulent messages, suspicious links, fake prize notifications, and calls requesting money, passwords, or personal information.

CyberAware AI addresses this problem by providing accessible cybersecurity education and practical digital safety guidance.

## 3. Proposed Solution

The platform provides four main features:

- Cybersecurity lessons.
- Interactive quizzes.
- An AI cybersecurity assistant.
- A scam awareness library.

## 4. IBM Db2 Integration

IBM Db2 is the planned central database for the application.

It is designed to store:

- Cybersecurity lessons.
- Quiz questions and answers.
- Learning progress.
- Educational resources.

Python connects to IBM Db2 using the `ibm_db` connector.

The database structure is provided in `database/schema.sql`.

**Status:** Database connection code and SQL schema have been prepared. A live IBM Db2 connection has not yet been verified.

## 5. AI Architecture

The project uses LangChain and Ollama to prepare an AI-powered cybersecurity assistant.

The intended workflow is:

1. A user submits a cybersecurity question.
2. The application retrieves relevant educational information.
3. The AI model generates an understandable response.
4. The application displays the response.

**Status:** AI integration code has been prepared but requires a running Ollama service and a configured model. It has not yet been tested.

## 6. Technology Stack

- Python
- Flask
- IBM Db2
- ibm_db
- LangChain
- LangChain Ollama
- HTML
- CSS
- JavaScript
- pytest

## 7. Project Structure

```text
cyberaware-ai/
│
├── app.py
├── ai.py
├── db.py
├── lessons.py
├── quiz.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── database/
│   └── schema.sql
│
├── templates/
│   └── index.html
│
└── tests/
    └── test_app.py
```

## 8. Installation and Setup

### Prerequisites

- Python 3.10 or later.
- IBM Db2 database access.
- Ollama installed for local AI functionality.

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file using `.env.example` as a guide.

Add your IBM Db2 credentials and Ollama configuration.

Never upload your real `.env` file or passwords to GitHub.

### Run the application

```bash
python app.py
```

Open your browser:

```text
http://localhost:5000
```

## 9. Database Setup

The database structure is provided in:

`database/schema.sql`

Execute this SQL file in your IBM Db2 environment to create the required tables and sample educational records.

Configure the connection credentials before testing database operations.

## 10. AI Setup

Install Ollama and download the configured model:

```bash
ollama pull qwen2.5-coder:0.5b
```

Start Ollama and run the Flask application.

Ensure the model name in `.env` matches the installed model.

## 11. Testing

Install dependencies:

```bash
pip install -r requirements.txt
```

Run automated tests:

```bash
pytest tests/
```

Tests are provided for the homepage, health endpoint, and cybersecurity assistant endpoint.

**Status:** Test files have been prepared. Successful test execution has not yet been confirmed.

## 12. Security Considerations

- Never request users' passwords or mobile money PINs.
- Never expose database credentials.
- Use environment variables for sensitive configuration.
- Encourage users to verify suspicious messages and links.
- Provide practical cybersecurity education.

## 13. Screenshots and Demo

Screenshots will be stored in:

`docs/screenshots/`

Demo video: To be added.

## 14. Future Improvements

- Support additional African languages.
- Expand scam examples relevant to African communities.
- Add user accounts and learning progress tracking.
- Improve AI responses using verified cybersecurity resources.
- Add more interactive cybersecurity quizzes.
- Introduce secure scam-reporting guidance.

## 15. Project Creator

**NGELI MALIKA MARIE**

GitHub: https://github.com/ngelimalika-ops

Role: Project design, development, and documentation.

---

CyberAware AI — Making cybersecurity education accessible to everyone.
