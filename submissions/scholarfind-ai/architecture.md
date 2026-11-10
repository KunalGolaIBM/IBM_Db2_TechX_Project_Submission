# ScholarFind AI Architecture

## Components
- Frontend: React and Vite
- Backend: Python FastAPI
- Database: IBM Db2
- Connector: ibm_db

## Data Flow
1. Student enters profile information.
2. React sends the information to FastAPI.
3. FastAPI processes the scholarship search.
4. The backend retrieves scholarship records from Db2 when configured.
5. Matching results are returned to the frontend.

## Architecture Diagram

Student
  |
  v
React Frontend
  |
  v
FastAPI Backend
  |
  v
IBM Db2 Database

## Current Status
Prototype. Db2 connectivity must be configured and tested.
