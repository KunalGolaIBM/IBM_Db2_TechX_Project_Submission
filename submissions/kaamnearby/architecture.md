# KaamNearby - Architecture Overview

## Overview
KaamNearby is a local service marketplace platform designed to connect customers with nearby skilled workers. The app allows users to search for services, compare worker profiles, send booking requests, negotiate prices, and manage the final service appointment.

## Core Components

### 1. Frontend Layer
- HTML pages for home, service search, booking, and worker profile views
- CSS for layout and mobile-friendly design
- JavaScript for form validation, category filtering, and dynamic interactions

### 2. Application Layer
- Flask server handles routing and business logic
- Service categories are managed via a simple backend model
- Booking and negotiation logic are processed through Flask endpoints

### 3. Data Layer
- SQLite database stores users, workers, services, bookings, and negotiation records
- Lightweight schema design keeps the prototype easy to run and maintain

## Main Workflow
1. Customer searches for a service category nearby.
2. Worker list is displayed based on location and service type.
3. Customer selects a worker and creates a booking request.
4. Price negotiation is discussed through the platform.
5. Booking status is updated as pending, accepted, or completed.

## Scalability Path
- Replace SQLite with IBM Db2 in enterprise deployment
- Add analytics, reporting, and worker performance dashboards
- Support real-time notifications and worker availability tracking

