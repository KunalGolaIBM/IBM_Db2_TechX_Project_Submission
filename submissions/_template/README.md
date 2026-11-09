
# CyberAware AI
## An AI-Powered Cybersecurity Awareness and Education Platform

### One-Line Pitch
CyberAware AI helps people understand online threats, recognize scams and phishing messages, and learn how to protect themselves online through lessons, quizzes, and an AI assistant.

## 1. Problem Statement
Many people use mobile money, social media, and online services without knowing how to identify cyber threats. They may receive fraudulent messages, fake links, and calls requesting money or personal information.

CyberAware AI addresses this problem by making cybersecurity education simple and accessible.

### Target Users
- Students and young people
- Parents
- Small business owners
- Mobile money users
- People with limited cybersecurity knowledge

## 2. Solution Overview

CyberAware AI is a web application with four main features:

1. Cybersecurity lessons explaining online safety.
2. Interactive quizzes to test cybersecurity knowledge.
3. An AI assistant that answers cybersecurity awareness questions.
4. A scam awareness library containing examples of common online scams and prevention tips.

## 3. IBM Db2 Integration

IBM Db2 is used as the application's database.

It stores:
- Cybersecurity lessons.
- Quiz questions and answers.
- Learning progress.
- Educational resources.

Python connects the application to IBM Db2 using the ibm_db driver.

## 4. AI Architecture

Framework: LangChain.

The AI assistant receives questions from users and uses relevant cybersecurity educational information to generate understandable answers.

The application retrieves educational information from IBM Db2 and provides it as context to the AI model.

## 5. Tech Stack

- Backend: Python
- Database: IBM Db2
- AI Framework: LangChain
- Frontend: HTML, CSS and JavaScript
- Database Connector: ibm_db

## 6. Prerequisites

- Python 3.10 or later
- IBM Db2 database access
- Required Python packages
- An AI model provider and API key

## 7. Setup and Installation

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file using `.env.example` as a guide.

Configure your IBM Db2 connection and AI provider credentials.

## 8. Running the Project

Run the application using:

```bash
python src/main.py
```

## 9. Testing and Verification

Run the tests using:

```bash
pytest tests/
```

## 10. Screenshots and Demo

Screenshots will be added to:

`docs/screenshots/`

Demo video link: To be added.

## 11. Known Limitations and Future Roadmap

- Initial lessons cover a limited number of cyber threats.
- AI answers depend on the available educational information.
- Future versions will support more languages.
- Future versions will include more scam examples relevant to African communities.

## 12. Team Members and Credits

Project Creator: NGELI MALIKA MARIE

GitHub: @ngelimalika-ops

Role: Project design, development, and documentation.
 
flask
ibm_db
python-dotenv
langchain
langchain-core
langchain-ollama
pytest
