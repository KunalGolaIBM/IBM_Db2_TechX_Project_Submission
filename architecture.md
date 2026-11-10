# ScholarFind AI – Architecture

## Overview
ScholarFind AI is a scholarship discovery platform that helps students
find scholarship opportunities based on their profile and eligibility.

## Architecture

- Frontend: React and Vite
- Backend: Python FastAPI
- Database: IBM Db2
- Database connectivity: ibm_db

## Application Flow

1. Students enter their profile and preferences.
2. The React frontend sends requests to the FastAPI backend.
3. The backend evaluates scholarship eligibility.
4. Scholarship data is retrieved from IBM Db2 when configured.
5. Matching scholarship results are returned to the frontend.

## Database
The database schema is provided in backend/schema.sql.

## Configuration
Database connection settings are supplied through environment variables.
See backend/.env.example.

## Current Implementation
The project includes a FastAPI backend and React frontend.
Sample data may be used when Db2 is not configured.
