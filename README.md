# IBM Db2 Developer Extension for VS Code (`ibm-db2-developer-extension`)

<div align="center">

![IBM Db2 Developer Extension Banner](https://img.shields.io/badge/IBM%20Db2-Developer%20Extension-0f62fe?style=for-the-badge&logo=ibm&logoColor=white)
<br/>

**Db2 DevTools — Enterprise Database Tooling Native to Visual Studio Code**

[![VS Code](https://img.shields.io/badge/Visual%20Studio%20Code-%5E1.80.0-007ACC?style=flat-square&logo=visual-studio-code&logoColor=white)](https://code.visualstudio.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Node.js](https://img.shields.io/badge/Node.js-%5E18.x%20%7C%20%5E20.x-339933?style=flat-square&logo=node.js&logoColor=white)](https://nodejs.org/)
[![Db2 Connector](https://img.shields.io/badge/Connector-ibm__db-052FAD?style=flat-square&logo=ibm&logoColor=white)](https://github.com/ibmdb/node-ibm_db)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)

</div>

---

## Table of Contents

- [1. Overview & Problem Statement](#1-overview--problem-statement)
  - [The Challenge](#the-challenge)
  - [The Solution](#the-solution)
  - [Why Db2 DevTools?](#why-db2-devtools)
- [2. Key Features](#2-key-features)
  - [Database Connection Management](#database-connection-management)
  - [Unified SQL Editor](#unified-sql-editor)
  - [Query Execution & Results Engine](#query-execution--results-engine)
  - [Database Explorer (Schema Tree)](#database-explorer-schema-tree)
  - [Feature Implementation Status Matrix](#feature-implementation-status-matrix)
- [3. Technology Stack](#3-technology-stack)
- [4. System Requirements](#4-system-requirements)
- [5. Installation Guide](#5-installation-guide)
  - [Option A: Build and Run from Source (Development Mode)](#option-a-build-and-run-from-source-development-mode)
  - [Option B: Package and Install via VSIX](#option-b-package-and-install-via-vsix)
- [6. Getting Started & Setup](#6-getting-started--setup)
  - [Step 1: Open the Extension](#step-1-open-the-extension)
  - [Step 2: Add a Db2 Connection Profile](#step-2-add-a-db2-connection-profile)
  - [Step 3: Secure Credential Storage](#step-3-secure-credential-storage)
  - [Step 4: Establish the Connection](#step-4-establish-the-connection)
  - [Step 5: Browse Database Objects](#step-5-browse-database-objects)
  - [Step 6: Write Your First Query](#step-6-write-your-first-query)
- [7. Usage Guide & Workflows](#7-usage-guide--workflows)
  - [Executing Queries](#executing-queries)
  - [Example SQL Queries](#example-sql-queries)
  - [Tabular Results & Exporting](#tabular-results--exporting)
  - [Query Execution History](#query-execution-history)
  - [Keyboard Shortcuts](#keyboard-shortcuts)
- [8. Project Architecture](#8-project-architecture)
  - [Directory Structure](#directory-structure)
  - [Core Subsystem Architecture](#core-subsystem-architecture)
- [9. Screenshots & Interface Previews](#9-screenshots--interface-previews)
  - [Extension Overview & Activity Bar](#extension-overview--activity-bar)
  - [Connection Profile Manager](#connection-profile-manager)
  - [SQL Editor & IntelliSense](#sql-editor--intellisense)
  - [Query Results Grid](#query-results-grid)
  - [Database Explorer Tree](#database-explorer-tree)
- [10. Security & Credential Hygiene](#10-security--credential-hygiene)
- [11. Troubleshooting & FAQ](#11-troubleshooting--faq)
- [12. Future Enhancements & Roadmap](#12-future-enhancements--roadmap)
- [13. Contributing](#13-contributing)
- [14. License](#14-license)
- [15. Acknowledgements](#15-acknowledgements)
- [16. Contact & Support](#16-contact--support)

---

## 1. Overview & Problem Statement

### The Challenge
Developers and database engineers working with **IBM Db2** frequently face workflow friction caused by tool fragmentation:
- **Disruptive Context Switching:** Writing application code in Visual Studio Code while relying on heavyweight external GUI tools (such as IBM Data Studio, DBeaver, or command-line `db2cli`) causes constant window toggling, keyboard shortcut conflicts, and mental overhead.
- **Inconvenient Terminal Workflows:** Command-line CLI scripts lack native tabular rendering, inline syntax autocomplete, hover documentation, and interactive schema inspection.
- **Insecure Credential Handling:** Developers frequently resort to saving raw database passwords in local text files, scratchpads, or unencrypted configuration objects.
- **Absence of Native Db2 Dialect Support in VS Code:** Generic SQL extensions lack Db2 catalog awareness (`SYSCAT` / `SYSIBM`), dialect-specific DDL/DML grammar, and native driver binding.

### The Solution
The **IBM Db2 Developer Extension for VS Code** (**Db2 DevTools**) bridges this gap by bringing an enterprise-grade, native Db2 development environment directly into Visual Studio Code. Built upon the VS Code Extension API and the official `ibm_db` native driver, it turns your editor into a high-performance Db2 cockpit for managing connections, inspecting database schemas, authoring queries with IntelliSense, and visualizing query results.

```
+-------------------------------------------------------------------------+
|                       VISUAL STUDIO CODE WORKSPACE                      |
|                                                                         |
|  +--------------------+  +--------------------+  +-------------------+  |
|  | Database Explorer  |  |   Db2 SQL Editor   |  |   Results Panel   |  |
|  | - Connections      |  | - Syntax Highlight |  | - Sortable Grid   |  |
|  | - Schemas / Tables |  | - Autocomplete     |  | - CSV / JSON      |  |
|  | - Views / Routines |  | - Query Validation |  | - Execution Stats |  |
|  +---------+----------+  +---------+----------+  +---------^---------+  |
|            |                       |                       |            |
|            +-----------------------+-----------------------+            |
|                                    |                                    |
|                        [ Db2 Extension Host ]                           |
|                    - Connection Pool & History                          |
|                    - SecretStorage (OS Keychain)                        |
|                    - ibm_db Native Engine                               |
+------------------------------------+------------------------------------+
                                     |  TCP/IP (Port 50000 / 50001 SSL)
                                     v
                  +--------------------------------------+
                  |            IBM Db2 Server            |
                  |  - Community Edition (Docker / Pod)  |
                  |  - Enterprise Server / Cloud / z/OS  |
                  +--------------------------------------+
```

### Why Db2 DevTools?
- **All-in-One Developer Experience:** Code, debug, query, and inspect data without ever leaving your editor.
- **Zero Insecure Configuration:** Automatic integration with operating system credential vaults via VS Code's `SecretStorage` API.
- **Native Db2 Dialect Knowledge:** Tailored for IBM Db2 SQL, built-in functions, administrative catalog views, and system pseudo-tables (`SYSIBM.SYSDUMMY1`).
- **Lightweight & Fast:** Asynchronous execution model ensures large query results do not block or freeze the editor UI.

---

## 2. Key Features

### Database Connection Management
- **Profile Creation & Storage:** Create multiple connection profiles targeting local Docker instances, staging servers, on-premises Db2 LUW deployments, or IBM Cloud Db2 databases.
- **Edit & Delete Profiles:** Update hostnames, ports, databases, or user profiles effortlessly from the connection panel.
- **Multiple Active Connections:** Maintain concurrent sessions across distinct environments (e.g., Development, QA, and Production) and switch execution targets seamlessly.
- **Hardware-Backed Credential Security:** Passwords and sensitive authentication tokens are **never** written to unencrypted configuration files. Credentials are saved directly to the host operating system's keychain using the **VS Code SecretStorage API**.

### Unified SQL Editor
- **Multi-Query Authoring & Execution:** Open `.sql` files or interactive scratchpads. Run the active query under the cursor or execute selected blocks with a single shortcut (`Cmd+Enter` / `Ctrl+Enter`).
- **Db2 Syntax Highlighting:** Comprehensive syntax tokenization for Db2 SQL, keywords, data types (`VARCHAR`, `CLOB`, `BLOB`, `VECTOR`, `DECFLOAT`), and built-in functions.
- **Context-Aware Autocomplete & Snippets:** IntelliSense completions for SQL clauses, table identifiers, and productive code templates (e.g., `CREATE TABLE`, `SELECT ... FETCH FIRST`, index creation).
- **Real-Time Syntax Validation:** Immediate diagnostics for mismatched clauses, syntax errors, and missing delimiters.
- **Parameter Signature Help:** Inline assistance showing parameter requirements for Db2 built-in scalar, aggregate, and mathematical functions.

### Query Execution & Results Engine
- **Direct Editor Execution:** Dispatch queries asynchronously to the Db2 server without blocking the VS Code extension host.
- **Interactive Tabular Results:** Query result sets render in a clean, scrollable, and sortable webview grid with dynamic column resizing and total row count tallies.
- **Data Export Utilities:** One-click export of result sets to standard **CSV** and formatted **JSON** files for downstream processing or reporting.
- **Execution Performance Metrics:** Live metrics displayed for every execution, including query elapsed time in milliseconds, row count, and execution status.
- **Query History Log:** Persistent workspace execution history capturing timestamps, query text, execution durations, and outcome statuses.

### Database Explorer (Schema Tree)
- **Hierarchical Tree Navigation:** Integrated directly into the VS Code Activity Bar with a dedicated Db2 view.
- **Rich Schema Object Inspection:** Drill down through database nodes:
  - **Schemas:** System and user schemas.
  - **Tables:** Columns, data types, nullability, primary and foreign keys.
  - **Views:** View definitions and dependent columns.
  - **Procedures & Functions:** Stored routines, input/output parameter profiles.
  - **Sequences & Indexes:** Database sequences and indexed attributes.
- **Object Context Menus:** Right-click context actions on any table or view:
  - *Select Top 100 Rows* (automatically crafts and runs `FETCH FIRST 100 ROWS ONLY`).
  - *Script as CREATE DDL*.
  - *Copy Object Name* to clipboard.
  - *Refresh Schema Node*.

### Feature Implementation Status Matrix

| Subsystem | Feature Capability | Status | Implementation Component |
|---|---|:---:|---|
| **Connections** | Profile Creation & Editing | Available | `src/connection/connectionManager.ts` |
| **Connections** | SecretStorage OS Keychain Vault | Available | `src/connection/credentialStore.ts` |
| **Connections** | Multi-Profile Active Switching | Available | `src/connection/connectionManager.ts` |
| **Connections** | SSL/TLS Encrypted Connection | Available | `src/connection/db2Driver.ts` |
| **SQL Editor** | Db2 SQL Syntax Highlighting | Available | `syntaxes/db2-sql.tmLanguage.json` |
| **SQL Editor** | Autocomplete & Code Snippets | Available | `src/editor/completionProvider.ts` |
| **SQL Editor** | Signature Help for Functions | Available | `src/editor/signatureHelp.ts` |
| **SQL Editor** | Real-Time Query Diagnostics | Available | `src/editor/diagnostics.ts` |
| **Execution** | Async Query Execution | Available | `src/connection/db2Driver.ts` |
| **Execution** | Tabular Webview Results Grid | Available | `src/webview/resultsPanel.ts` |
| **Execution** | Export Results (CSV & JSON) | Available | `src/webview/exportService.ts` |
| **Execution** | Query Execution History View | Available | `src/history/historyManager.ts` |
| **Explorer** | Schemas, Tables, Views Tree | Available | `src/explorer/dbTreeDataProvider.ts` |
| **Explorer** | Procedures, Triggers & Sequences | Available | `src/explorer/schemaIntrospector.ts` |
| **Explorer** | Context Menu (Select Top 100, DDL) | Available | `package.json` (menus & commands) |
| **Advanced** | Visual EXPLAIN Plan Graph | Roadmap | Planned for v0.2.0 |
| **Advanced** | Interactive Stored Procedure Debugger | Roadmap | Planned for v0.3.0 |

---

## 3. Technology Stack

Db2 DevTools leverages industry-standard TypeScript and the Visual Studio Code extension ecosystem:

```
+--------------------------------------------------------------------------+
|                            TECHNOLOGY STACK                              |
+--------------------------------------------------------------------------+
| Extension Runtime       | Visual Studio Code Extension API (v1.80.0+)    |
| Core Language           | TypeScript 5.x (Strict Type Checking)          |
| Platform Runtime        | Node.js (v18.x / v20.x Active LTS)             |
| Db2 Connectivity Engine | ibm_db (Native IBM Db2 driver for Node.js)     |
| Credential Vault        | VS Code SecretStorage API (OS Keyring Bridge)  |
| UI Webview Layer        | VS Code Webview API, HTML5, CSS Grid, Vanilla JS|
| Build & Bundler         | npm, tsc (TypeScript Compiler), @vscode/vsce   |
| Code Quality & Testing  | ESLint, Prettier, Mocha, @vscode/test-electron |
+--------------------------------------------------------------------------+
```

---

## 4. System Requirements

Before installing and building the extension, verify that your development environment satisfies the following minimum requirements:

### Developer Workstation
- **Operating System:**
  - macOS (Apple Silicon ARM64 via native or Rosetta, or Intel x64)
  - Linux (Ubuntu 20.04+, Debian 11+, RHEL/CentOS 8+, Fedora)
  - Windows 10 or 11 (64-bit)
- **Visual Studio Code:** Version `^1.80.0` or later.
- **Node.js:** `v18.16.0+` or `v20.x` LTS.
- **Package Manager:** `npm` v9.x or higher.
- **Native Build Prerequisites (for compiling `ibm_db`):**
  - **macOS:** Xcode Command Line Tools (`xcode-select --install`).
  - **Linux:** GCC/G++, Make, and Python 3 (`sudo apt install build-essential python3`).
  - **Windows:** Visual Studio C++ Build Tools or Windows SDK.

### Target IBM Db2 Database Server
- **Supported Db2 Editions:**
  - IBM Db2 Community Edition (v11.5 / v12.1+ running locally via Docker or Podman)
  - IBM Db2 Standard / Advanced Enterprise Server Edition (on-premises or cloud VM)
  - IBM Cloud Db2 / Db2 Warehouse on Cloud
  - IBM watsonx.data Db2 Engine
- **Network Accessibility:** Accessible TCP/IP port (`50000` for unencrypted, `50001` for TLS/SSL).

---

## 5. Installation Guide

### Option A: Build and Run from Source (Development Mode)

If you are developing or contributing to the extension, follow these steps to run the extension in the VS Code **Extension Development Host**:

#### 1. Clone the Repository
```bash
git clone https://github.com/vanshikayadav6153-ai/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission
```

#### 2. Open in VS Code
```bash
code .
```

#### 3. Install Node.js Dependencies
```bash
npm install
```
> **Note:** During `npm install`, the `ibm_db` package downloads and configures the native IBM Db2 CLI/ODBC driver binaries appropriate for your operating system.

#### 4. Compile the TypeScript Source
You can perform a one-time build or start the incremental watch compiler:
```bash
# One-time build
npm run compile

# Or start the incremental watch mode for development
npm run watch
```

#### 5. Launch the Extension Development Host
1. Press `F5` on your keyboard (or navigate to the **Run & Debug** view in the Activity Bar and select **Run Extension**).
2. A new window titled **[Extension Development Host]** will launch with the IBM Db2 Developer Extension actively loaded.
3. Verify that the **Db2 DevTools** icon is visible in the Activity Bar on the left side of the screen.

---

### Option B: Package and Install via VSIX

To distribute and install the extension as a self-contained `.vsix` package:

#### 1. Install the VS Code Extension Manager (`@vscode/vsce`)
```bash
npm install -g @vscode/vsce
```

#### 2. Package the Extension
```bash
vsce package
# Outputs: ibm-db2-developer-extension-0.1.0.vsix
```

#### 3. Install the Package into VS Code
**Via Command Line:**
```bash
code --install-extension ibm-db2-developer-extension-0.1.0.vsix
```

**Via VS Code Graphical Interface:**
1. Open Visual Studio Code.
2. Open the **Extensions** view (`Ctrl+Shift+X` or `Cmd+Shift+X`).
3. Click the three-dot menu (**...**) in the top right corner of the Extensions panel.
4. Select **Install from VSIX...**
5. Choose `ibm-db2-developer-extension-0.1.0.vsix` and confirm installation.

---

## 6. Getting Started & Setup

Follow this step-by-step walkthrough to configure your first connection and explore a database.

### Step 1: Open the Extension
Click on the **Db2 DevTools** icon in the VS Code Activity Bar (located on the far left). This opens the **Database Explorer** and **Query History** sidebars.

### Step 2: Add a Db2 Connection Profile
1. In the **Db2 Connections** panel, click the **+ (Add Connection)** icon in the title bar.
2. An interactive configuration form will display prompting for connection parameters:

| Field Name | Description | Example Value |
|---|---|---|
| **Profile Name** | User-friendly identifier for the profile | `Local Db2 Docker` |
| **Host Name / IP** | Hostname or IP address of the Db2 server | `localhost` or `127.0.0.1` |
| **Port Number** | Database listener port (Standard: 50000, SSL: 50001) | `50000` |
| **Database Name** | Name of the target database | `testdb` |
| **Username** | Database authentication user ID | `db2inst1` |
| **Password** | User account password | *(Managed securely in Step 3)* |
| **Use SSL / TLS** | Check to enable encrypted transport | `false` (Local) / `true` (Cloud) |

> [!WARNING]
> Never hardcode or save actual database passwords into repository files or `.vscode/settings.json`. Always rely on the extension's secure credential prompt.

### Step 3: Secure Credential Storage
When saving a profile or connecting for the first time, the extension prompts for your password via an input box with masked characters:
```
+--------------------------------------------------------------------+
| Enter password for db2inst1@localhost:50000/testdb: [ ********** ] |
+--------------------------------------------------------------------+
```
- The password is saved directly to the **VS Code SecretStorage API**.
- Under the hood, SecretStorage delegates to your operating system's native secure keyring:
  - **macOS:** Apple Keychain
  - **Windows:** Windows Credential Manager
  - **Linux:** Secret Service API / `libsecret` (GNOME Keyring / KWallet)

### Step 4: Establish the Connection
1. Right-click your newly created profile and select **Connect**, or double-click the profile node.
2. A green status indicator appears next to the profile name indicating an active, healthy session.
3. Connection metadata (Server Version, Instance Name, Code Page) is retrieved from the server.

### Step 5: Browse Database Objects
Expand the active connection tree to explore:
- **Schemas:** View `SYSCAT`, `SYSIBM`, and user-defined schemas.
- **Tables:** Expand any schema to view all user tables. Click on a table to inspect columns, data types, lengths, and constraints.
- **Views:** Inspect database views and definitions.
- **Stored Procedures & Routines:** Review procedure signatures and parameter lists.

### Step 6: Write Your First Query
1. Click the **New SQL Scratchpad** button in the top action bar, or create a new file named `query.sql`.
2. Ensure the active connection profile is set in the bottom status bar (`Db2: Local Db2 Docker [testdb]`).
3. Type your SQL query and execute it immediately.

---

## 7. Usage Guide & Workflows

### Executing Queries

Db2 DevTools provides flexible execution modes:
1. **Execute Query Under Cursor:** Place your cursor inside any SQL statement and press `Ctrl+Enter` (Windows/Linux) or `Cmd+Enter` (macOS). The extension automatically detects statement boundaries delineated by semicolons.
2. **Execute Selected Text:** Highlight any arbitrary SQL snippet and press `Ctrl+Enter` / `Cmd+Enter`.
3. **Execute Entire File:** Use the command palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run `Db2: Execute All Statements`.

### Example SQL Queries

#### 1. System Verification & Environment Metadata
```sql
-- Verify active database server, date, and timestamp
SELECT 
    CURRENT DATE AS current_date,
    CURRENT TIME AS current_time,
    CURRENT SERVER AS server_name,
    CURRENT TIMEZONE AS timezone_offset
FROM SYSIBM.SYSDUMMY1;
```

#### 2. Querying User Tables
```sql
-- Query application data with column filtering and limits
SELECT 
    id,
    first_name,
    last_name,
    email,
    created_at
FROM DB2INST1.CUSTOMERS
WHERE status = 'ACTIVE'
ORDER BY created_at DESC
FETCH FIRST 50 ROWS ONLY;
```

#### 3. Inspecting the Db2 System Catalog (`SYSCAT`)
```sql
-- List all user tables in the database with their row counts and table spaces
SELECT 
    TABSCHEMA,
    TABNAME,
    TYPE,
    TBSPACE,
    COLCOUNT
FROM SYSCAT.TABLES
WHERE TABSCHEMA NOT LIKE 'SYS%'
ORDER BY TABSCHEMA, TABNAME;
```

#### 4. Introspecting Column Definitions for a Table
```sql
-- Inspect column metadata for a target table
SELECT 
    COLNAME,
    TYPENAME,
    LENGTH,
    SCALE,
    NULLS
FROM SYSCAT.COLUMNS
WHERE TABSCHEMA = 'DB2INST1' AND TABNAME = 'CUSTOMERS'
ORDER BY COLNO ASC;
```

---

### Tabular Results & Exporting

When a query executes successfully, the **Db2 Results Panel** automatically opens:

```
+-----------------------------------------------------------------------------------------+
| Db2 Query Results: SELECT * FROM DB2INST1.CUSTOMERS       [ Export CSV ] [ Export JSON ]|
| Status: SUCCESS | Rows: 3 | Execution Time: 42 ms                                       |
+-----+------------+-----------+----------------------+-----------------------------------+
| ID  | FIRST_NAME | LAST_NAME | EMAIL                | CREATED_AT                        |
+-----+------------+-----------+----------------------+-----------------------------------+
| 101 | Sarah      | Connor    | sconnor@cyber.io     | 2026-10-15 09:30:00               |
| 102 | Miles      | Dyson     | mdyson@cyber.io      | 2026-10-16 11:14:22               |
| 103 | John       | Connor    | jconnor@resist.org   | 2026-10-17 14:02:45               |
+-----+------------+-----------+----------------------+-----------------------------------+
```

- **Interactive Sorting:** Click on any column header to sort in ascending or descending order.
- **Export to CSV:** Click **Export CSV** to serialize the active result set into a comma-separated values file and select a destination folder.
- **Export to JSON:** Click **Export JSON** to generate a structured JSON array of row objects.

---

### Query Execution History

Every executed statement is logged in the **Query History** panel:
- **Timestamp:** Exact execution time.
- **Status:** Visual indicator (`SUCCESS` in green, `FAILED` with error code in red).
- **Execution Time:** Duration in milliseconds (`ms`).
- **Query Text:** Full SQL statement string.
- **1-Click Re-run:** Click the **Run** icon on any historical entry to reload and execute the query instantly in the active editor.

---

### Keyboard Shortcuts

| Shortcut (macOS) | Shortcut (Windows/Linux) | Action |
|---|---|---|
| `Cmd+Enter` | `Ctrl+Enter` | Execute current query or selected block |
| `Cmd+Alt+N` | `Ctrl+Alt+N` | Open a new Db2 SQL Scratchpad |
| `Cmd+Alt+R` | `Ctrl+Alt+R` | Refresh Database Explorer schema tree |
| `Cmd+Shift+P` -> `Db2: Connect` | `Ctrl+Shift+P` -> `Db2: Connect` | Quick connect to selected profile |
| `Cmd+Shift+P` -> `Db2: Export` | `Ctrl+Shift+P` -> `Db2: Export` | Export current result set to file |

---

## 8. Project Architecture

### Directory Structure

The repository is structured following VS Code extension engineering best practices:

```text
ibm-db2-developer-extension/
├── .github/                       # GitHub Actions workflows & issue templates
│   ├── workflows/
│   │   └── ci.yml                 # Automated test & build validation pipeline
│   ├── ISSUE_TEMPLATE/            # Bug report and feature request templates
│   └── PULL_REQUEST_TEMPLATE.md   # Standardized pull request template
├── .vscode/                       # Workspace-specific VS Code development settings
│   ├── launch.json                # Launch configuration for Extension Development Host
│   └── tasks.json                 # Build, watch, and test execution tasks
├── media/                         # Webview assets and icon artwork
│   ├── icons/
│   │   ├── db2-activity.svg       # Activity bar primary icon
│   │   ├── connection.svg         # Connection profile icon
│   │   ├── table.svg              # Database table item icon
│   │   └── view.svg               # Database view item icon
│   ├── results.css                # Styling for tabular results webview
│   └── results.js                 # Dynamic table sorting and event handlers
├── syntaxes/                      # TextMate grammars for syntax tokenization
│   └── db2-sql.tmLanguage.json    # Db2 SQL grammar, keywords, and data types
├── snippets/                      # Code snippets and templates
│   └── db2-sql.json               # DDL/DML templates (CREATE, SELECT, INSERT)
├── src/                           # TypeScript source code
│   ├── extension.ts               # Main extension entry point (activate / deactivate)
│   ├── connection/                # Database connectivity & security layer
│   │   ├── connectionManager.ts   # Connection pooling and profile life cycle
│   │   ├── credentialStore.ts     # VS Code SecretStorage wrapper (OS keychain)
│   │   ├── db2Driver.ts           # ibm_db native driver abstraction wrapper
│   │   └── types.ts               # Profile and connection interface definitions
│   ├── explorer/                  # TreeView Database Explorer provider
│   │   ├── dbTreeDataProvider.ts  # Implementation of vscode.TreeDataProvider
│   │   ├── treeNodes.ts           # Hierarchy of TreeItem classes (Schema, Table, etc.)
│   │   └── schemaIntrospector.ts  # Db2 catalog metadata engine (SYSCAT views)
│   ├── editor/                    # SQL language features and intelligence
│   │   ├── completionProvider.ts  # Autocomplete engine for keywords & identifiers
│   │   ├── signatureHelp.ts       # Function parameter signatures
│   │   └── diagnostics.ts         # SQL syntax diagnostics and linter
│   ├── webview/                   # Query results visualization
│   │   ├── resultsPanel.ts        # Results WebviewPanel lifecycle and messaging
│   │   └── exportService.ts       # CSV and JSON formatting and export
│   └── history/                   # Execution history tracker
│       └── historyManager.ts      # Query execution persistence and log manager
├── test/                          # Unit and integration test suites
│   ├── suite/
│   │   ├── connection.test.ts     # Connection manager and credential tests
│   │   ├── query.test.ts          # Driver execution and parsing tests
│   │   └── extension.test.ts      # Extension activation integration tests
│   ├── runTest.ts                 # Test runner using @vscode/test-electron
│   └── index.ts                   # Mocha test configuration
├── .editorconfig                  # Formatting rules for editors
├── .eslintrc.json                 # TypeScript ESLint static analysis rules
├── .gitignore                     # Git ignore rules for node_modules, dist, etc.
├── package.json                   # Extension manifest (contributes, scripts, engines)
├── tsconfig.json                  # TypeScript compiler options
├── CHANGELOG.md                   # Release history and version updates
├── CONTRIBUTING.md                # Contribution guidelines and setup instructions
├── LICENSE                        # Open-source license terms (Apache-2.0)
├── README.md                      # Comprehensive developer documentation
└── SECURITY.md                    # Vulnerability reporting and credential guidelines
```

---

### Core Subsystem Architecture

The extension is organized into five decoupled subsystems:

```
                      +----------------------------------+
                      |       src/extension.ts           |
                      |   (Extension Lifecycle Hooks)    |
                      +-----------------+----------------+
                                        |
      +--------------------+------------+------------+--------------------+
      |                    |                         |                    |
      v                    v                         v                    v
+---------------+  +---------------+         +---------------+   +---------------+
|  connection/  |  |   explorer/   |         |    editor/    |   |   webview/    |
| - connManager |  | - treeProvider|         | - completion  |   | - resultsPanel|
| - credStore   |  | - introspect  |         | - diagnostics |   | - export      |
| - db2Driver   |  | - treeNodes   |         | - signature   |   +-------+-------+
+-------+-------+  +-------+-------+         +-------+-------+           |
        |                  |                         |                   |
        +------------------+-------------------------+                   |
                           |                                             |
                           v                                             v
               [ ibm_db Native Engine ]                     [ HTML5 Results View ]
                           |
                           v
                 [ IBM Db2 Database ]
```

1. **Extension Lifecycle (`src/extension.ts`):** Registers commands, binds language providers, initializes tree providers, and manages clean teardown during deactivation.
2. **Connection Layer (`src/connection/`):** Manages connection lifecycle and profile persistence. Interacts with `SecretStorage` to ensure secrets are isolated in the OS keyring. Wraps `ibm_db` to maintain reliable connection pools.
3. **Database Explorer (`src/explorer/`):** Implements `vscode.TreeDataProvider`. Queries `SYSCAT.TABLES`, `SYSCAT.COLUMNS`, `SYSCAT.VIEWS`, and `SYSCAT.ROUTINES` to construct an on-demand tree view with minimal memory overhead.
4. **SQL Editor Services (`src/editor/`):** Implements `vscode.CompletionItemProvider` and `vscode.SignatureHelpProvider` to provide real-time auto-completion for Db2 keywords, schema objects, and SQL functions.
5. **Webview Results Engine (`src/webview/`):** Renders interactive HTML/CSS data grids inside a `vscode.WebviewPanel`. Handles bidirectional postMessage communication for sorting, pagination, and file exports.

---

## 9. Screenshots & Interface Previews

### Extension Overview & Activity Bar
The extension integrates directly into the primary VS Code workspace alongside your active code editors.

```text
+--------------------------------------------------------------------------------------------+
| [Db2]  EXPLORER                   | query.sql                             | RESULTS        |
|-----------------------------------|---------------------------------------|----------------|
| v DB2 CONNECTIONS                 | SELECT                                | STATUS: OK     |
|   v Production (db2inst1@db2srv)  |   TABSCHEMA,                          | ROWS: 2        |
|     v Schemas                     |   TABNAME,                            | TIME: 18ms     |
|       v DB2INST1                  |   COLCOUNT                            |----------------|
|         v Tables                  | FROM SYSCAT.TABLES                    | SCHEMA | TABLE |
|           > CUSTOMERS             | WHERE TABSCHEMA = 'DB2INST1'          |--------+-------|
|           > ORDERS                | FETCH FIRST 10 ROWS ONLY;             | DB2INS | CUST  |
|           > INVENTORY             |                                       | DB2INS | ORDR  |
|         > Views                   |                                       |                |
|         > Procedures              |                                       |                |
|                                   |                                       |                |
| v QUERY HISTORY                   |                                       |                |
|   * [14:22:01] SUCCESS (18ms)     |                                       |                |
|   * [14:20:15] SUCCESS (32ms)     |                                       |                |
+--------------------------------------------------------------------------------------------+
```

---

### Connection Profile Manager
Add, edit, or remove connection configurations using a structured form:

```text
+-------------------------------------------------------------------------+
|                        Add New Db2 Connection                           |
+-------------------------------------------------------------------------+
| Profile Name:      [ Local Docker Db2                                 ] |
| Host Name / IP:    [ localhost                                        ] |
| Port:              [ 50000                                            ] |
| Database:          [ testdb                                           ] |
| User:              [ db2inst1                                         ] |
| Password:          [ ********************                             ] |
| Connection Type:   (o) Standard TCP/IP      ( ) SSL / TLS Encrypted     |
|                                                                         |
|                    [ Test Connection ]   [ Save Profile ]   [ Cancel ]  |
+-------------------------------------------------------------------------+
```

---

### SQL Editor & IntelliSense
Instant completions for Db2 keywords, schema tables, and built-in routines:

```text
+-------------------------------------------------------------------------+
| 1 | SELECT * FROM SYSIBM.SYSDUMMY1;                                     |
| 2 |                                                                     |
| 3 | SELECT c.ID, c.NAME, c.STATUS                                       |
| 4 | FROM DB2INST1.CUST                                                  |
|   |                 +---------------------------------------------+     |
|   |                 | CUSTOMERS       (Table) - DB2INST1.CUSTOMERS|     |
|   |                 | CUSTOMER_LOGS   (Table) - DB2INST1.CUST_LOGS|     |
|   |                 | CUST_SUMMARY    (View)  - DB2INST1.SUMMARY  |     |
|   |                 +---------------------------------------------+     |
+-------------------------------------------------------------------------+
```

---

### Query Results Grid
Fast, responsive tabular presentation with export controls:

```text
+-------------------------------------------------------------------------+
| Results (DB2INST1.CUSTOMERS)               [ Export CSV ] [ Export JSON]|
+-------------------------------------------------------------------------+
| ID (int)  | FIRST_NAME (varchar) | LAST_NAME (varchar) | BALANCE (dec)  |
+-----------+----------------------+---------------------+----------------+
| 1001      | Alice                | Smith               | 12450.00       |
| 1002      | Bob                  | Johnson             | 8320.50        |
| 1003      | Charlie              | Brown               | 410.25         |
+-------------------------------------------------------------------------+
| Showing 3 of 3 rows | Elapsed time: 24 ms                               |
+-------------------------------------------------------------------------+
```

---

### Database Explorer Tree
Browse schemas, columns, constraints, and stored routines with a single click:

```text
+------------------------------------------------------+
| v DB2 CONNECTIONS                                    |
|   v Local Docker Db2 (Connected)                     |
|     v Schemas                                        |
|       v DB2INST1                                     |
|         v Tables                                     |
|           v CUSTOMERS                                |
|             - ID: INTEGER NOT NULL [PK]              |
|             - FIRST_NAME: VARCHAR(64)                |
|             - LAST_NAME: VARCHAR(64)                 |
|             - EMAIL: VARCHAR(128)                    |
|             - CREATED_AT: TIMESTAMP                  |
|           > ORDERS                                   |
|         > Views                                      |
|         > Stored Procedures                          |
+------------------------------------------------------+
```

---

## 10. Security & Credential Hygiene

Db2 DevTools is engineered in alignment with enterprise security guidelines and follows zero-trust credential practices:

```
+-------------------------------------------------------------------------+
|                      CREDENTIAL SECURITY WORKFLOW                       |
+-------------------------------------------------------------------------+
|  User Enters Password ---> VS Code SecretStorage API                    |
|                                    |                                    |
|                                    v                                    |
|                    Host OS Credential Keystore                          |
|             +-----------------------------------------+                 |
|             | macOS Keychain                          |                 |
|             | Windows Credential Manager              |                 |
|             | Linux Secret Service (libsecret/GNOME)  |                 |
|             +--------------------+--------------------+                 |
|                                  |                                      |
|                                  v                                      |
|                Retrieved in-memory ONLY at connect                      |
|                NEVER written to disk, settings, or logs                 |
+-------------------------------------------------------------------------+
```

### Security Guardrails
1. **No Clear-Text Passwords on Disk:** Database passwords are **never** persisted in VS Code workspace `settings.json`, global settings, or configuration files.
2. **OS Keychain Encryption:** All sensitive authentication secrets are encrypted at rest by the operating system's native keychain infrastructure via `vscode.ExtensionContext.secrets`.
3. **Connection Security:** Full support for TLS/SSL encrypted connections (`Security=SSL`, `SSLServerCertificate`).
4. **Parameterized Catalog Inquiries:** All schema introspection queries against `SYSCAT` use parameterized bindings to prevent SQL injection vulnerabilities.
5. **No Telemetry of Query Contents:** The extension never transmits query strings, table contents, or schema metadata to external servers or third-party analytical endpoints.

---

## 11. Troubleshooting & FAQ

### Common Issues & Resolutions

#### 1. Native Driver Compilation / `ibm_db` Installation Error
- **Symptom:** `npm install` fails with `node-gyp rebuild` error or `clang: error: linker command failed`.
- **Cause:** Missing C/C++ compilation toolchain or Python 3 in your development path.
- **Resolution:**
  - **macOS:** Run `xcode-select --install` to install Xcode developer tools. For Apple Silicon (M1/M2/M3), verify that Node.js is matching your native terminal architecture (`node -p "process.arch"` should return `arm64`).
  - **Linux:** Install build tools:
    ```bash
    sudo apt update && sudo apt install -y build-essential python3
    ```
  - **Windows:** Run `npm install --global --production windows-build-tools` or install Visual Studio C++ Desktop Development tools.

#### 2. Connection Refused: `SQL30081N` Communication Link Failure
- **Symptom:** Connecting to `localhost:50000` returns `SQL30081N: A communication error has been detected`.
- **Cause:** The Db2 database container or server service is not running or the port is blocked.
- **Resolution:**
  - Check whether the Db2 Docker container is running:
    ```bash
    docker ps | grep db2
    ```
  - Verify container startup has completed:
    ```bash
    docker logs db2server | grep "Setup has completed"
    ```
  - Verify port `50000` is exposed: `nc -zv localhost 50000` or `telnet localhost 50000`.

#### 3. Authentication Failed: `SQL30082N` (Security Processing Failed)
- **Symptom:** Error `SQL30082N Security processing failed with reason 24 (USERNAME AND/OR PASSWORD INVALID)`.
- **Cause:** Incorrect username or password, or user account locked.
- **Resolution:**
  - Verify your password in the container:
    ```bash
    docker exec -it db2server su - db2inst1
    ```
  - In VS Code, clear the saved credential using `Db2: Reset Saved Credentials for Profile` and re-enter your password.

#### 4. SSL Handshake Error
- **Symptom:** `SQL30081N SSL handshake failed`.
- **Cause:** Connecting to an SSL port (`50001`) with SSL disabled, or a missing self-signed CA certificate.
- **Resolution:**
  - Enable **Use SSL / TLS** in the connection profile.
  - If using self-signed certificates, specify the path to your CA certificate in the profile settings.

#### 5. Extension Command Not Found
- **Symptom:** Running a Db2 command returns `command 'db2.connect' not found`.
- **Cause:** The extension failed to activate during launch.
- **Resolution:**
  - Open **Help > Toggle Developer Tools** in VS Code.
  - Inspect the **Console** tab for activation stack traces.
  - Ensure `npm run compile` was executed before pressing `F5`.

---

## 12. Future Enhancements & Roadmap

The following capabilities are planned for upcoming releases:

- [ ] **Visual Explain & Query Execution Plan:**
  - Graphical node-based visualization of `EXPLAIN` query plans showing index scans, table scans, join strategies, and cost estimations.
- [ ] **Interactive Stored Procedure Debugger:**
  - Breakpoints, variable inspection, and step-through debugging for Db2 SQL PL stored procedures and user-defined functions (UDFs).
- [ ] **AI-Assisted Query Generation (watsonx.ai Integration):**
  - Natural-language-to-SQL synthesis powered by IBM watsonx.ai Granite models, grounded against the active Db2 catalog.
- [ ] **Schema Migration & Diff Tool:**
  - Compare two schemas across environments (e.g., Staging vs. Production) and generate migration DDL change scripts.
- [ ] **Data Import Wizard:**
  - Direct import from CSV, JSON, and Excel spreadsheets into Db2 tables with automatic column type inference.
- [ ] **Interactive Db2 Notebooks (`.db2book`):**
  - Native VS Code Interactive Notebook support allowing markdown notes interspersed with executable Db2 SQL cells.

---

## 13. Contributing

We welcome community contributions, bug reports, and pull requests! To contribute:

### 1. Fork the Repository
Fork this repository to your personal GitHub account:
```bash
git clone https://github.com/<your-username>/ibm-db2-developer-extension.git
cd ibm-db2-developer-extension
git remote add upstream https://github.com/vanshikayadav6153-ai/ibm-db2-developer-extension.git
```

### 2. Create a Topic Branch
```bash
git checkout -b feature/your-feature-name
```

### 3. Implement Your Changes
- Follow standard TypeScript strict-mode conventions.
- Keep components modular and single-responsibility.
- Ensure all new public methods have JSDoc comments.

### 4. Run Code Quality Checks & Tests
```bash
# Run linter
npm run lint

# Run automated tests
npm run test
```

### 5. Submit a Pull Request
- Push your topic branch: `git push origin feature/your-feature-name`.
- Open a Pull Request against `main`.
- Fill out the PR template describing your changes, motivation, and test verification results.

---

## 14. License

This project is licensed under the **Apache License, Version 2.0**.  
See the [LICENSE](LICENSE) file for the full license text.

```text
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## 15. Acknowledgements

- **IBM Db2 Team:** For providing enterprise-grade database technology and maintaining the official [`ibm_db`](https://github.com/ibmdb/node-ibm_db) Node.js connector.
- **Visual Studio Code Team (Microsoft):** For the extensible VS Code platform and extension APIs.
- **Open-Source Community:** For providing foundational tools, packages, and continuous feedback.

---

## 16. Contact & Support

- **Issue Tracker:** [GitHub Issues](https://github.com/vanshikayadav6153-ai/ibm-db2-developer-extension/issues)
- **Discussions & Feedback:** [GitHub Discussions](https://github.com/vanshikayadav6153-ai/ibm-db2-developer-extension/discussions)
- **Documentation Guide:** See the [`docs/`](docs/) directory for detailed environment setup and Db2 container provisioning guides.

---

<div align="center">
  <sub>Built with ❤️ for the IBM Db2 and Visual Studio Code developer community.</sub>
</div>
