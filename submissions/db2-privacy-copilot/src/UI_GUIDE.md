# UI Guide - Multi-Page Streamlit App

## 🎨 New Professional UI

The Db2 Privacy Copilot now has a **professional multi-page flow** with authentication and role-based access.

---

## 📱 Page Flow

```
Landing Page (/)
    ↓
Login Page (3 roles)
    ↓
Dashboard (role-specific)
    ↓
Feature Pages (Discovery, Classification, Consents, Requests, Audit)
```

---

## 🚀 Getting Started

### 1. **Landing Page** (`app.py`)

**URL**: http://localhost:8501

Features:
- Hero section with gradient background
- Key features showcase (6 cards)
- How it works (4-step process)
- Technology stack
- DPDP decision-support scope (not legal advice)
- CTA button to launch dashboard

**Actions**:
- Click "🚀 Launch Dashboard" → Goes to Login

---

### 2. **Login Page** (`pages/1_🔐_Login.py`)

**3 Pre-configured Roles**:

| Role | User | Permissions |
|------|------|-------------|
| **VIEWER** | Alice Johnson | Read-only access to all pages |
| **ANALYST** | Bob Smith | Create requests, manage consents, run classification |
| **DPO** | Charlie Davis | Full access, approve requests, execute erasure |

**Actions**:
- Click "Login as VIEWER/ANALYST/DPO"
- Session stored in `st.session_state`
- Redirects to Dashboard

**Demo Mode**: No password needed — just click the role button

---

### 3. **Dashboard** (`pages/2_📊_Dashboard.py`)

**Features**:
- Welcome message with user name
- 4 metric cards (Tables, PII Columns, Pending Requests, Audit Records)
- Quick actions (role-based)
- Recent activity feed (last 10 audit records)
- System health indicators
- Tips & best practices (role-specific)

**Sidebar Navigation**:
- Shows current user info
- Links to all pages
- Logout button

**Quick Actions** (role-based):
- **VIEWER**: View-only metrics
- **ANALYST**: Run Discovery, Classify PII, Create Request
- **DPO**: Review Requests, Verify Audit Chain, Manage Rules

---

### 4. **Discovery Page** (`pages/3_🔍_Discovery.py`)

**Purpose**: Map database schema automatically

**Actions**:
1. Click "🔄 Scan Schema"
2. See tables with columns
3. View foreign key relationships
4. Check statistics

**Output**:
- List of tables (4 in mock mode: PATIENT, APPOINTMENT, PRESCRIPTION, LAB_REPORT)
- Column details (name, type, nullable)
- FK graph (child → parent)
- Metrics: table count, column count, FK count

---

### 5. **Classification Page** (`pages/4_🏷️_Classification.py`)

**Purpose**: Detect PII columns using AI

**Actions**:
1. Click "🔍 Run Classification"
2. See results grouped by PII type
3. Check confidence scores
4. Review flagged columns

**Output**:
- Total columns classified
- PII columns found (EMAIL, PHONE, NAME, DOB, GOVT_ID)
- Columns needing manual review
- Confidence percentages
- Detection method (VALUE_RULE, NAME_VECTOR)

---

### 6. **Consents Page** (`pages/5_✅_Consents.py`)

**Purpose**: Bitemporal consent tracking

**3 Tabs**:

**Tab 1: Grant Consent**
- Enter patient ID
- Select purpose (MARKETING, RESEARCH, TREATMENT, ANALYTICS)
- Set start and end dates
- Click "Grant Consent"

**Tab 2: Withdraw Consent**
- Enter patient ID
- Select purpose
- Set effective date
- Click "Withdraw Consent"

**Tab 3: View Consents**
- Enter patient ID
- Click "Load Consents"
- See active consents with validity periods

**Bitemporal Tracking**:
- Business time: when was consent valid?
- System time: when did we know about it?

---

### 7. **Requests Page** (`pages/6_🗑️_Requests.py`)

**Purpose**: Data subject rights requests (erasure)

**2 Tabs**:

**Tab 1: Create Request**
- Enter subject ID (patient ID)
- Click "📋 Generate Plan"
- See dry-run plan:
  - Total steps
  - Total rows affected
  - Per-table actions (ERASE, ANONYMISE, RETAIN)
  - Reasons from retention rules
  - Verification status
  - Plan hash (binds to approval)

**Tab 2: Approve Requests** (DPO only)
- List of pending requests
- Review plan details
- Approve or reject
- Execute approved plans

**Safety**:
- Dry-run only (no execution without approval)
- Guardrail validates SQL
- Single transaction with rollback
- Audit trail records everything

---

### 8. **Audit Log Page** (`pages/7_📝_Audit.py`)

**Purpose**: Tamper-evident audit trail

**Features**:
- **Verify Chain** button: Check SHA256 hash chain integrity
- Recent records slider (10-100)
- Expandable record details:
  - Actor, action, subject
  - Timestamp, hash
  - JSON detail payload

**Hash Chain**:
- Each record contains hash(previous_hash + content)
- Tampering with any record breaks the chain
- Verification detects:
  - Missing GENESIS
  - Hash mismatches
  - Chain breaks

---

## 🎨 Design System

### Colors
- **Primary**: `#667eea` (purple-blue)
- **Secondary**: `#764ba2` (deep purple)
- **Success**: `#28a745` (green)
- **Warning**: `#ffc107` (yellow)
- **Error**: `#dc3545` (red)
- **Background**: `#f8f9fa` (light gray)

### Typography
- **Headings**: Bold, large (2-3.5em)
- **Body**: 1-1.2em, line-height 1.6
- **Captions**: 0.9em, color `#666`

### Components
- **Cards**: White background, rounded corners, shadow on hover
- **Buttons**: Full width, gradient, large font
- **Metrics**: Large number, small label, colored
- **Badges**: Rounded pills with status colors

---

## 🔐 Authentication Flow

```python
# Session State Variables
st.session_state.authenticated = True/False
st.session_state.user_role = "VIEWER" | "ANALYST" | "DPO"
st.session_state.user_name = "Alice Johnson"
st.session_state.user_email = "alice@example.com"
```

**Protection**:
- Every page checks `authenticated` status
- Redirects to login if not authenticated
- Logout clears session and redirects to landing

**Role Enforcement**:
- Dashboard shows role-specific quick actions
- Some pages require specific roles (e.g., DPO for approvals)
- Buttons disabled for insufficient permissions

---

## 🛠️ Customization

### Adding a New Page

1. Create `ui/pages/X_🔥_YourPage.py`
2. Number determines order (1, 2, 3...)
3. Emoji shows in sidebar
4. Add auth check at top:
   ```python
   if 'authenticated' not in st.session_state or not st.session_state.authenticated:
       st.warning("Please log in first")
       st.switch_page("pages/1_🔐_Login.py")
       st.stop()
   ```
5. Add navigation button to Dashboard sidebar

### Changing Colors

Edit CSS in each page's `st.markdown("""<style>...</style>""", unsafe_allow_html=True)`

### Adding Users

Edit `users` dict in `pages/1_🔐_Login.py`:
```python
users = {
    "NEW_ROLE": {
        "name": "John Doe",
        "email": "john@example.com",
        "desc": "Description",
        "permissions": ["List of permissions"]
    }
}
```

---

## 📊 Page Statistics

| Page | Lines | Components | Features |
|------|-------|------------|----------|
| Landing | 250 | Hero, Cards, Stats | Marketing-focused |
| Login | 180 | Role cards, Auth | Session management |
| Dashboard | 280 | Metrics, Actions, Feed | Role-based UI |
| Discovery | 120 | Scanner, Results | FK graph viz |
| Classification | 100 | Runner, Results | Confidence scores |
| Consents | 140 | 3 tabs, Forms | Bitemporal |
| Requests | 130 | Planner, Approver | Dry-run safety |
| Audit | 90 | Verifier, Records | Hash chain |

**Total**: ~1,290 lines across 8 pages

---

## 🚀 Performance

- **Load time**: <1s (mock mode)
- **Navigation**: Instant (no page reloads)
- **Session**: Persists across page changes
- **Responsive**: Works on mobile (but optimized for desktop)

---

## 🐛 Troubleshooting

### "Please log in first" on every page
- Session state cleared
- Click "Go to Login" and log in again

### Sidebar not showing
- Check `initial_sidebar_state` in `st.set_page_config()`
- Should be "expanded" for feature pages

### Navigation buttons not working
- Ensure all pages are in `ui/pages/` directory
- Filenames must start with number (e.g., `1_`, `2_`)

### Styling not applied
- Check `unsafe_allow_html=True` in `st.markdown()`
- Verify CSS syntax

---

## 📚 Next Steps

### Enhancements:
1. **Database mode toggle**: Switch between mock and real Db2
2. **Export functionality**: Download reports as PDF/CSV
3. **Dark mode**: Add theme switcher
4. **Real-time updates**: WebSocket for live metrics
5. **User management**: Add/edit/remove users
6. **API integration**: Call FastAPI from UI instead of direct module imports
7. **Visualizations**: Add charts (Plotly/Altair)
8. **Search**: Filter/search in audit log and requests

---

## 📖 Resources

- **Streamlit Docs**: https://docs.streamlit.io/
- **Multi-page Apps**: https://docs.streamlit.io/library/get-started/multipage-apps
- **Session State**: https://docs.streamlit.io/library/api-reference/session-state
- **Custom CSS**: https://docs.streamlit.io/library/api-reference/utilities/st.markdown

---

**Status**: ✅ All 8 pages created and functional  
**Mode**: Mock (in-memory demo data)  
**URL**: http://localhost:8501  
**Version**: 1.0.0
