# SmartBite — AI-Powered Food Rescue Platform

**SmartBite** is an AI-powered food rescue and redistribution platform connecting restaurants with surplus food to verified NGOs in real time.

The platform couples a high-performance **Python FastAPI** backend with an intuitive, accessible **Next.js 16 (React 19 + TypeScript)** frontend, authenticated via **Clerk**.

---

## Architecture & Project Structure

SmartBite is structured as a fullstack repository containing the FastAPI backend service and the Next.js frontend application:

```
FoodRescueBackEnd/
├── app/                             # FastAPI Backend Service (Port 8000)
│   ├── main.py                      # FastAPI app initialization, CORS, lifespan migration, routers
│   ├── config.py                    # Pydantic BaseSettings with Clerk configuration & validation
│   ├── database.py                  # PostgreSQL engine, sessionmaker, Base, and get_db dependency
│   ├── models/                      # SQLAlchemy ORM models (User, Restaurant, NGO, Donation, Match)
│   ├── schemas/                     # Pydantic v2 validation and response schemas
│   ├── routes/                      # 8 Modular API routers (26 endpoints)
│   │   ├── health.py                # Public health & DB probe
│   │   ├── auth.py                  # /auth/me and onboarding endpoints
│   │   ├── users.py                 # User query endpoints
│   │   ├── restaurants.py           # Restaurant profile management
│   │   ├── ngos.py                  # NGO organization management
│   │   ├── donations.py             # Food donation lifecycle & history endpoints
│   │   ├── matches.py               # Matching & offer workflow endpoints
│   │   └── forecasting.py           # 7-day demand forecasting & model evaluation
│   └── services/                    # Core business logic & algorithms
│       ├── auth.py                  # Clerk JWKS RS256 token verification & role dependencies
│       ├── matching.py              # 7-factor explainable AI matching engine & Haversine distance
│       ├── workflow.py              # State machine lifecycle, atomic accept/reject logic
│       └── forecasting.py           # Nutritional demand baseline & historical intake blender
├── frontend/                        # Next.js 16 Frontend Application (Port 3000)
│   ├── app/
│   │   ├── dashboard/
│   │   │   ├── ngo/page.tsx         # NGO portal (pending match offers, atomic accept/reject)
│   │   │   └── restaurant/page.tsx  # Restaurant portal (active listings, AI match inspect)
│   │   ├── donations/new/page.tsx   # Surplus food listing creation form
│   │   ├── forecasts/page.tsx       # AI demand forecasting & model transparency
│   │   ├── onboarding/page.tsx      # Role selection & profile registration
│   │   ├── sign-in/[[...sign-in]]/  # Clerk Sign-In route
│   │   ├── sign-up/[[...sign-up]]/  # Clerk Sign-Up route
│   │   ├── globals.css              # Tailwind styles and theme tokens
│   │   ├── layout.tsx               # Root layout with ClerkProvider & Navbar
│   │   └── page.tsx                 # SmartBite landing page
│   ├── components/                  # UI design system (Button, Badge, Card, Input, Select, Navbar, Footer)
│   ├── lib/
│   │   ├── api.ts                   # Centralized typed API client for FastAPI communication
│   │   └── types.ts                 # TypeScript domain types mirroring backend schemas
│   ├── middleware.ts                # Clerk route protection middleware
│   ├── .env.example                 # Frontend template environment variables
│   └── package.json                 # Next.js dependencies and build scripts
├── tests/                           # Pytest automated test suites (63 tests)
├── .env.example                     # Backend template environment variables
├── .gitignore                       # Root ignore rules for Python and Node
├── package.json                     # Root proxy scripts (npm run dev/build from root)
├── requirements.txt                 # Pinned Python package dependencies
└── README.md                        # Complete project documentation
```

---

## How to Start the Applications

### 1. Start the FastAPI Backend

From the workspace root directory:

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the FastAPI server (runs on http://127.0.0.1:8000)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health at [http://localhost:8000/health](http://localhost:8000/health).  
Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Start the Next.js Frontend

In a separate terminal window:

```bash
# Option A: From root directory using proxy scripts
npm run dev

# Option B: From frontend directory
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Required Environment Variables

### Backend Configuration (`.env` in workspace root)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Description | Example / Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres@localhost:5432/food_rescue_db` |
| `CORS_ORIGINS` | Permitted frontend origins | `http://localhost:3000,http://127.0.0.1:3000` |
| `CLERK_PUBLISHABLE_KEY` | Clerk Publishable Key | `pk_test_...` |
| `CLERK_SECRET_KEY` | Clerk Secret Key (keep secure!) | `sk_test_...` |
| `CLERK_JWKS_URL` | Clerk JWKS public keys URL | `https://your-subdomain.clerk.accounts.dev/.well-known/jwks.json` |
| `CLERK_ISSUER` | Expected JWT `iss` claim | `https://your-subdomain.clerk.accounts.dev` |

### Frontend Configuration (`frontend/.env.local`)

Copy `frontend/.env.example` to `frontend/.env.local`:

```bash
cp frontend/.env.example frontend/.env.local
```

| Variable | Description | Example / Default |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Public publishable key for Clerk SDK | `pk_test_...` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | Route for Clerk sign-in | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | Route for Clerk sign-up | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | Destination after sign-in | `/onboarding` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | Destination after sign-up | `/onboarding` |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of FastAPI backend | `http://localhost:8000` |
| `NEXT_PUBLIC_API_URL` | Fallback alias for API URL | `http://localhost:8000` |

> [!SECURITY NOTE]
> Never put `CLERK_SECRET_KEY` or database connection strings into `frontend/.env.local` or client-side bundles.

---

## How to Configure the Clerk Application

1. Visit the [Clerk Dashboard](https://dashboard.clerk.com) and create or select your application.
2. In **API Keys**:
   - Copy **Publishable Key** $\rightarrow$ set as `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in `frontend/.env.local` and `CLERK_PUBLISHABLE_KEY` in root `.env`.
   - Copy **Secret Key** $\rightarrow$ set as `CLERK_SECRET_KEY` in root `.env`.
3. In **Developers > API Keys**, locate your **Frontend API URL** (e.g., `https://example-app.clerk.accounts.dev`):
   - Set `CLERK_ISSUER` to `https://example-app.clerk.accounts.dev`.
   - Set `CLERK_JWKS_URL` to `https://example-app.clerk.accounts.dev/.well-known/jwks.json`.
4. Under **Configure > User & Authentication > Email, Phone, Username**, ensure email authentication is active.

---

## How the Two Applications Communicate

```
┌──────────────────────────────────────┐                   ┌──────────────────────────────────────┐
│         Next.js 16 Frontend          │                   │           FastAPI Backend            │
│       (http://localhost:3000)        │                   │       (http://localhost:8000)        │
│                                      │                   │                                      │
│  1. User signs in via Clerk UI       │                   │                                      │
│  2. lib/api.ts fetches session token │                   │                                      │
│     using Clerk getToken()           │                   │                                      │
│  3. Sends HTTP Request with header:  │                   │                                      │
│     Authorization: Bearer <token>    ├─ HTTP / JSON ────►│ 4. Verifies RS256 token against      │
│                                      │                   │    cached Clerk JWKS public keys     │
│                                      │                   │ 5. Resolves User ID & User Role      │
│                                      │                   │ 6. Executes DB query or AI engine    │
│  8. Renders typed data / shows alert ◄─ JSON Response ───┤ 7. Returns typed Pydantic response   │
└──────────────────────────────────────┘                   └──────────────────────────────────────┘
```

1. **Authentication Token**: The frontend never handles passwords or database credentials. It calls Clerk's `getToken()` hook and transmits the JWT in the standard `Authorization: Bearer <token>` header.
2. **Server-Side Verification**: FastAPI verifies the JWT signature using Clerk's public JWKS endpoint (`RS256`), checks expiration (`exp`) and issuer (`iss`), and matches `sub` against the `users.clerk_id` database index.
3. **Role & Resource Authorization**: FastAPI strictly validates roles (`restaurant` vs `ngo`) and ownership constraints on every request before modifying any state.
4. **Typed Contract**: `frontend/lib/types.ts` mirrors all backend Pydantic schemas, and `frontend/lib/api.ts` provides typed methods for all 26 endpoints.

---

## UI Sections Connection Status

### Connected to Real Backend API Endpoints

- **`/onboarding`**: Calls `GET /auth/me` to check onboarding status, and `POST /auth/onboard/restaurant` or `POST /auth/onboard/ngo` to complete registration.
- **`/dashboard/restaurant`**: Calls `GET /donations/` to retrieve listings, `GET /matches/donation/{id}` to fetch AI matches with scoring factors, `POST /matches/donation/{id}/offers` to send batch offers, and `POST /donations/{id}/cancel` to cancel listings.
- **`/dashboard/ngo`**: Calls `GET /matches/pending` to load real-time incoming offers, `POST /matches/{id}/accept` to accept an offer, `POST /matches/{id}/reject` to decline an offer, and `PATCH /donations/{id}/status` to update delivery progress.
- **`/donations/new`**: Submits new food listings to `POST /donations/` with category, portions, and expiration timestamps.
- **`/forecasts`**: Calls `GET /forecasts/aggregate?days={d}` for network demand, `GET /forecasts/ngo/{id}?days={d}` for individual NGO forecasts, and `GET /forecasts/evaluation` for data readiness status.

### Mocked or Incomplete Sections

- **Landing Page Impact Counter** (`frontend/app/page.tsx`): Displays labeled illustrative statistics ("12,400+ Meals Rescued") to demonstrate presentation pending an aggregate historical totals API.
- **Interactive Route Map**: Geographic pickup routes display coordinate information; live interactive map tiles require third-party map provider API keys (e.g. Mapbox/Google Maps).
- **Long-term Historical Trends**: For NGOs with fewer than 5 historical donations, the forecast UI displays the baseline demand explanation, in accordance with the backend's `insufficient_history` status.

---

## Step 4 & 5 Backend Reference

### Role & Endpoint Access Matrix

| Endpoint | Method | Role Required | Constraint |
|---|---|---|---|
| `/health` | `GET` | Public | Connectivity probe |
| `/auth/me` | `GET` | Authenticated | Current user profile |
| `/auth/onboard/restaurant` | `POST` | Authenticated | First-time registration |
| `/auth/onboard/ngo` | `POST` | Authenticated | First-time registration |
| `/donations/` | `POST` | `restaurant` | Sets `restaurant_id` automatically |
| `/donations/` | `GET` | Authenticated | Returns visible donations |
| `/donations/{id}` | `GET` | Authenticated | Returns donation detail |
| `/donations/{id}/cancel` | `POST` | `restaurant` | Owner only |
| `/donations/{id}/status` | `PATCH` | `restaurant` or `ngo` | Restricted to parties involved |
| `/matches/donation/{id}` | `GET` | `restaurant` | Owner only |
| `/matches/donation/{id}/offers` | `POST` | `restaurant` | Owner only |
| `/matches/pending` | `GET` | `ngo` | Caller's NGO only |
| `/matches/{id}/accept` | `POST` | `ngo` | Target NGO only |
| `/matches/{id}/reject` | `POST` | `ngo` | Target NGO only |
| `/forecasts/ngo/{ngo_id}` | `GET` | `ngo` | Owner only (`ngo.id == ngo_id`) |
| `/forecasts/aggregate` | `GET` | Authenticated | Network-wide demand summaries |
| `/forecasts/evaluation` | `GET` | Authenticated | Model readiness metrics |

---

## Quality Checks & Automated Verification

### Backend Pytest Suite (63/63 Passed)

```bash
.venv/bin/pytest -v
```

- **Step 1 (7 tests)**: Core CRUD and health endpoints (`test_api.py`)
- **Step 2 (15 tests)**: 7-factor explainable AI matching & Lagos scenario (`test_matching.py`)
- **Step 3 (10 tests)**: State machine transitions, atomic accept/reject concurrency (`test_workflow.py`)
- **Step 4 (14 tests)**: Clerk RS256 token verification, RBAC, tenant isolation (`test_auth.py`)
- **Step 5 (17 tests)**: 7-day demand forecasting, baseline handling, model evaluation (`test_forecasting.py`)

### Frontend Build & Lint Checks

```bash
# Type check and production build
npm run build

# ESLint checks
npm run lint
```
