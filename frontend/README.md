# SmartBite Frontend

Modern Next.js 16 (React 19 + TypeScript + Tailwind CSS v4) frontend for **SmartBite** — an AI-powered food rescue and redistribution platform connecting restaurants with surplus food to verified NGOs in real time.

---

## Architecture & Communication Overview

SmartBite is architected as two decoupled, independently deployable services:

1. **Frontend (Next.js 16)**: Handles UI rendering, user interaction, client-side route protection via Clerk, and requests data from the backend via a centralized typed API client (`frontend/lib/api.ts`).
2. **Backend (FastAPI)**: Serves 26 RESTful endpoints across 8 routers, verifies RS256 JWT tokens using Clerk's JWKS public keys, runs the 7-factor explainable AI matching engine, executes atomic state machine transactions, and computes demand forecasts.

### How the Two Applications Communicate

```
┌─────────────────────────────────┐                 ┌─────────────────────────────────┐
│     Next.js 16 Frontend         │                 │         FastAPI Backend         │
│     (http://localhost:3000)     │                 │     (http://localhost:8000)     │
│                                 │                 │                                 │
│  1. User authenticates via      │                 │                                 │
│     Clerk SDK                   │                 │                                 │
│  2. lib/api.ts retrieves session│                 │                                 │
│     token: getToken()           │                 │                                 │
│  3. fetch() with Bearer token ──┼─ HTTP / JSON ──►│  4. Validates RS256 JWT via     │
│                                 │                 │     Clerk JWKS public key       │
│                                 │                 │  5. Resolves User & Role        │
│                                 │                 │  6. Runs business logic & ORM   │
│  8. Updates React state / UI  ◄─┼─ JSON Response ─┼──7. Returns typed response      │
└─────────────────────────────────┘                 └─────────────────────────────────┘
```

- **Transport**: Standard HTTP/1.1 or HTTP/2 carrying JSON payloads.
- **Authentication Header**: `Authorization: Bearer <session_token>` obtained dynamically via Clerk's client SDK. No tokens or secrets are stored in cookies or localStorage manually.
- **CORS**: Backend allows origins configured in `CORS_ORIGINS` (including `http://localhost:3000`).
- **Error Handling**: Non-2xx responses are parsed into typed `ApiError` instances containing the HTTP status code, error detail, and field-level validation errors.

---

## Environment Variables Configuration

Create a `.env.local` file inside the `frontend/` directory:

```bash
cp .env.example .env.local
```

### Required Frontend Environment Variables

| Variable | Description | Example / Default |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Public publishable key for your Clerk application. | `pk_test_...` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | Route for Clerk sign-in page. | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | Route for Clerk sign-up page. | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | Post-sign-in redirect destination. | `/onboarding` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | Post-sign-up redirect destination. | `/onboarding` |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the FastAPI backend. | `http://localhost:8000` |
| `NEXT_PUBLIC_API_URL` | Fallback alias for backend base URL. | `http://localhost:8000` |

> [!SECURITY NOTE]
> **Never** expose `CLERK_SECRET_KEY` in frontend code, client bundles, or `frontend/.env.example`. The secret key belongs exclusively in the backend `.env`.

---

## How to Configure the Clerk Application

1. Log into your [Clerk Dashboard](https://dashboard.clerk.com).
2. Create or select your SmartBite project.
3. Under **Configure > API Keys**, copy the **Publishable Key** into `frontend/.env.local`:
   ```env
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
   ```
4. Under **Configure > User & Authentication > Email, Phone, Username**, ensure **Email address** authentication is enabled.
5. In **Paths** (or via environment variables), confirm:
   - Sign-in URL: `/sign-in`
   - Sign-up URL: `/sign-up`
   - After sign-in URL: `/onboarding`
   - After sign-up URL: `/onboarding`

---

## How the Frontend Resolves the API URL

The API client in `frontend/lib/api.ts` resolves backend endpoints through `resolveEndpointUrl()`:

1. **Server-Side Runtime (SSR, Server Actions, Route Handlers)**: Reads the internal Vercel service binding from `process.env.BACKEND_URL` to route requests privately without crossing the public internet.
2. **Client-Side in Production on Vercel**: Uses relative `/api` paths matching the top-level Vercel rewrite (`/api/(.*)` $\rightarrow$ backend service) so browser requests are same-origin without CORS overhead.
3. **Explicit Override**: Honors `NEXT_PUBLIC_API_BASE_URL` or `NEXT_PUBLIC_API_URL` if set.
4. **Local Development Fallback**: Defaults to `http://localhost:8000` when running standalone dev servers.

To redirect the frontend to a remote or staged backend, set in `.env.local`:
```env
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com
```

---

## Quickstart: Running the Application

### 1. Start the Backend

From the workspace root directory:

```bash
# Ensure Python virtual environment is activated
source .venv/bin/activate

# Start the FastAPI server on port 8000
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health at: [http://localhost:8000/health](http://localhost:8000/health).

### 2. Start the Frontend

Open a second terminal window:

```bash
cd frontend
npm install
npm run dev
```

Alternatively, from the workspace root (using proxy scripts):

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Frontend Integration Status

### Connected UI Sections (Integrated with Real Backend APIs)

| Page / Component | Route | Backend API Endpoint | Description |
|---|---|---|---|
| **Onboarding Flow** | `/onboarding` | `GET /auth/me`<br>`POST /auth/onboard/restaurant`<br>`POST /auth/onboard/ngo` | Queries user status; registers new restaurant or NGO profiles with address and dietary criteria. |
| **Restaurant Dashboard** | `/dashboard/restaurant` | `GET /donations/`<br>`GET /matches/donation/{id}`<br>`POST /matches/donation/{id}/offers`<br>`POST /donations/{id}/cancel` | Loads active donations; fetches explainable AI matches with 7 scoring factors; triggers batch offers. |
| **NGO Dashboard** | `/dashboard/ngo` | `GET /matches/pending`<br>`POST /matches/{id}/accept`<br>`POST /matches/{id}/reject`<br>`PATCH /donations/{id}/status` | Reviews incoming surplus match offers; one-click atomic accept/reject; marks donations picked up or distributed. |
| **Donation Creation** | `/donations/new` | `POST /donations/` | Submits new surplus food listings with portions, kg quantity, and prep/expiry timestamps. |
| **Demand Forecasting** | `/forecasts` | `GET /forecasts/aggregate?days={d}`<br>`GET /forecasts/ngo/{id}?days={d}`<br>`GET /forecasts/evaluation` | Horizon toggles (3, 7, 14, 30 days), nutritional category breakdowns, and data readiness metrics. |

### UI Sections that Remain Mocked or Incomplete

| UI Section | Status | Explanation & Fallback Behavior |
|---|---|---|
| **Landing Page Hero Metrics** (`frontend/app/page.tsx`) | Illustrative | Displays static community impact statistics (e.g. "12,400+ Meals Rescued", "85+ Partner Kitchens"). Labeled explicitly as illustrative metrics until network-wide aggregate reporting endpoint is deployed. |
| **Map Visualization** | Incomplete | Interactive geographic maps showing real-time pickup routes currently display placeholder coordinate cards. Haversine distance calculations are accurately handled on the backend (`distance_km`). |
| **Historical Donation Analytics** | Incomplete | Deep multi-year historical trend charts on `/forecasts` fallback gracefully to baseline beneficiary demand when fewer than 5 historical donations exist for an NGO (`insufficient_history` flag from backend). |

---

## Quality Checks & Build Validation

Run these commands to verify frontend integrity:

```bash
# Type check and build Next.js production bundle
npm run build

# Run ESLint quality checks
npm run lint

# Start production server
npm run start
```
