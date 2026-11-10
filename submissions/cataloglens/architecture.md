# CatalogLens Architecture

## Overview

CatalogLens connects to IBM Db2, retrieves catalog metadata, analyzes schema structure, and presents findings through an interactive interface.

## Architecture

    User
      |
      v
    Streamlit Frontend
      |
      v
    FastAPI Backend
      |
      +------> IBM Db2 Catalog
      |          |
      |          +--> Tables, columns, keys, constraints, indexes
      |
      +------> LangGraph Analysis Workflow
                    |
                    v
              Relationship Analysis
                    |
              +-----+------+
              |            |
              v            v
        Declared Facts   Inferred Candidates
              |            |
              +-----+------+
                    |
                    v
             Evidence-aware Results

## Components

### Db2 integration
The IBM Db2 Python driver (`ibm_db`) connects to Db2 and retrieves schema metadata from system catalog views.

### FastAPI backend
Provides endpoints for database health, schema exploration, table metadata, and relationship analysis.

### Analysis workflow
LangGraph organizes the analysis workflow. Deterministic heuristic reasoning provides a fallback when an optional language-model API is not configured.

### Relationship analysis
CatalogLens distinguishes declared foreign-key relationships from heuristic candidates requiring manual verification.

### Streamlit frontend
Provides an interactive dashboard and schema explorer.

## Evidence and limitations

The application separates database facts from heuristic interpretations. Inferred relationships must not be treated as confirmed constraints.

The included database uses synthetic sample business records. The application demonstrates live connectivity to IBM Db2 Community Edition.

Anthropic Claude is optional and is not required for the deterministic fallback workflow.

## Security

Credentials and API keys are supplied through environment variables. Local `.env` files and secrets must not be committed.
