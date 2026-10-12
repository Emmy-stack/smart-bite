import type {
  HealthCheckResponse,
  AuthMeResponse,
  OnboardRestaurantRequest,
  OnboardNGORequest,
  User,
  Restaurant,
  RestaurantCreate,
  NGO,
  NGOCreate,
  FoodDonation,
  FoodDonationCreate,
  DonationStatus,
  DonationMatchResponse,
  DonationMatchesListResponse,
  MatchOfferResponse,
  MatchActionResponse,
  BatchOfferRequest,
  AggregateForecastResponse,
  NGOForecastResponse,
  ModelEvaluationResponse,
} from "./types";

/**
 * Resolves the target URL for an API endpoint across different execution environments:
 * 1. Server-side runtime (Route Handlers, Server Actions, SSR):
 *    Uses the Vercel internal service binding injected into `process.env.BACKEND_URL`.
 * 2. Explicit public URL:
 *    Uses `process.env.NEXT_PUBLIC_API_BASE_URL` or `process.env.NEXT_PUBLIC_API_URL`.
 * 3. Client-side browser in unified deployment (e.g. Vercel multi-service):
 *    Uses relative `/api` path which matches top-level rewrite `/api/(.*)` -> backend service.
 * 4. Local standalone development fallback:
 *    Uses `http://localhost:8000`.
 */
export function resolveEndpointUrl(endpoint: string): string {
  const cleanPath = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  // 1. Server-side runtime: read Vercel service binding
  if (typeof window === "undefined" && process.env.BACKEND_URL) {
    const base = process.env.BACKEND_URL.replace(/\/$/, "");
    return `${base}${cleanPath}`;
  }

  // 2. Explicit public environment variable
  const explicitBase =
    process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  if (explicitBase) {
    const base = explicitBase.replace(/\/$/, "");
    return `${base}${cleanPath}`;
  }

  // 3. Client-side browser in production / Vercel (same-origin rewrite)
  if (typeof window !== "undefined") {
    // If not running on local standalone Next.js dev port 3000
    if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      return `/api${cleanPath}`;
    }
  }

  // 4. Standalone local development fallback
  return `http://localhost:8000${cleanPath}`;
}

/**
 * Structured API Error containing HTTP status code and parsed backend error detail.
 */
export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Internal HTTP request helper.
 * Attaches Authorization header when token is supplied.
 * Throws ApiError on non-2xx responses. Never fakes success.
 */
async function request<T>(
  endpoint: string,
  options: {
    method?: string;
    token?: string | null;
    body?: unknown;
    headers?: Record<string, string>;
  } = {}
): Promise<T> {
  const { method = "GET", token, body, headers = {} } = options;

  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...headers,
  };

  if (token) {
    reqHeaders["Authorization"] = `Bearer ${token}`;
  }

  const url = resolveEndpointUrl(endpoint);

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: reqHeaders,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (networkError) {
    throw new ApiError(
      `Network connection failed. Could not reach SmartBite backend at ${url}.`,
      0,
      networkError
    );
  }

  if (!res.ok) {
    let errData: unknown;
    let errMsg = `Request failed with HTTP ${res.status}`;
    try {
      errData = await res.json();
      if (typeof errData === "object" && errData !== null && "detail" in errData) {
        const detail = (errData as { detail: unknown }).detail;
        if (typeof detail === "string") {
          errMsg = detail;
        } else if (Array.isArray(detail)) {
          errMsg = detail
            .map((d: { loc?: string[]; msg?: string }) => {
              const field = d.loc ? d.loc.slice(1).join(".") : "";
              return field ? `${field}: ${d.msg}` : d.msg || "Validation error";
            })
            .join("; ");
        }
      }
    } catch {
      // Non-JSON response body
    }
    throw new ApiError(errMsg, res.status, errData);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}

/**
 * Centralized, typed SmartBite API Client.
 * All methods correspond strictly to verified FastAPI routes.
 */
export const api = {
  // ---------------- Health & Diagnostics ----------------
  health: {
    /** GET /health - Check server and database status */
    check: () => request<HealthCheckResponse>("/health"),
  },

  // ---------------- Authentication & Onboarding ----------------
  auth: {
    /** GET /auth/me - Retrieve current verified user and onboarding status */
    getMe: (token: string) => request<AuthMeResponse>("/auth/me", { token }),

    /** POST /auth/onboard/restaurant - Onboard user as Restaurant partner */
    onboardRestaurant: (token: string, payload: OnboardRestaurantRequest) =>
      request<AuthMeResponse>("/auth/onboard/restaurant", {
        method: "POST",
        token,
        body: payload,
      }),

    /** POST /auth/onboard/ngo - Onboard user as verified NGO */
    onboardNGO: (token: string, payload: OnboardNGORequest) =>
      request<AuthMeResponse>("/auth/onboard/ngo", {
        method: "POST",
        token,
        body: payload,
      }),
  },

  // ---------------- Users ----------------
  users: {
    /** GET /users - List users with pagination (requires auth) */
    list: (token: string, params?: { skip?: number; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.skip !== undefined) q.append("skip", params.skip.toString());
      if (params?.limit !== undefined) q.append("limit", params.limit.toString());
      const qs = q.toString() ? `?${q.toString()}` : "";
      return request<User[]>(`/users${qs}`, { token });
    },

    /** GET /users/{id} - Get user by ID (requires auth) */
    getById: (token: string, userId: number) =>
      request<User>(`/users/${userId}`, { token }),
  },

  // ---------------- Restaurants ----------------
  restaurants: {
    /** GET /restaurants - List restaurants with pagination (requires auth) */
    list: (token: string, params?: { skip?: number; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.skip !== undefined) q.append("skip", params.skip.toString());
      if (params?.limit !== undefined) q.append("limit", params.limit.toString());
      const qs = q.toString() ? `?${q.toString()}` : "";
      return request<Restaurant[]>(`/restaurants${qs}`, { token });
    },

    /** GET /restaurants/{id} - Get restaurant by ID (requires auth) */
    getById: (token: string, restaurantId: number) =>
      request<Restaurant>(`/restaurants/${restaurantId}`, { token }),

    /** POST /restaurants - Create restaurant profile for authenticated user */
    create: (token: string, payload: RestaurantCreate) =>
      request<Restaurant>("/restaurants", { method: "POST", token, body: payload }),
  },

  // ---------------- NGOs ----------------
  ngos: {
    /** GET /ngos - List NGOs with pagination (requires auth) */
    list: (token: string, params?: { skip?: number; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.skip !== undefined) q.append("skip", params.skip.toString());
      if (params?.limit !== undefined) q.append("limit", params.limit.toString());
      const qs = q.toString() ? `?${q.toString()}` : "";
      return request<NGO[]>(`/ngos${qs}`, { token });
    },

    /** GET /ngos/{id} - Get NGO by ID (requires auth) */
    getById: (token: string, ngoId: number) =>
      request<NGO>(`/ngos/${ngoId}`, { token }),

    /** POST /ngos - Create NGO profile for authenticated user */
    create: (token: string, payload: NGOCreate) =>
      request<NGO>("/ngos", { method: "POST", token, body: payload }),
  },

  // ---------------- Donations ----------------
  donations: {
    /**
     * GET /donations - List surplus food donations with filtering
     */
    list: (
      token: string,
      params?: {
        status?: DonationStatus;
        restaurant_id?: number;
        skip?: number;
        limit?: number;
      }
    ) => {
      const q = new URLSearchParams();
      if (params?.status) q.append("status", params.status);
      if (params?.restaurant_id) q.append("restaurant_id", params.restaurant_id.toString());
      if (params?.skip !== undefined) q.append("skip", params.skip.toString());
      if (params?.limit !== undefined) q.append("limit", params.limit.toString());
      const qs = q.toString() ? `?${q.toString()}` : "";
      return request<FoodDonation[]>(`/donations${qs}`, { token });
    },

    /** GET /donations/{id} - Get single donation by ID */
    getById: (token: string, donationId: number) =>
      request<FoodDonation>(`/donations/${donationId}`, { token }),

    /** POST /donations - Create surplus food donation listing */
    create: (token: string, payload: FoodDonationCreate) =>
      request<FoodDonation>("/donations", { method: "POST", token, body: payload }),

    /** GET /donations/{id}/matches - Restaurant views match offers history for their donation */
    getMatchHistory: (token: string, donationId: number) =>
      request<DonationMatchesListResponse>(`/donations/${donationId}/matches`, { token }),

    /** PATCH /donations/{id}/status - Progress donation status */
    updateStatus: (token: string, donationId: number, targetStatus: DonationStatus) =>
      request<FoodDonation>(`/donations/${donationId}/status`, {
        method: "PATCH",
        token,
        body: { status: targetStatus },
      }),

    /** POST /donations/{id}/cancel - Cancel an active donation */
    cancel: (token: string, donationId: number) =>
      request<FoodDonation>(`/donations/${donationId}/cancel`, {
        method: "POST",
        token,
      }),
  },

  // ---------------- Matching & Offers ----------------
  matches: {
    /**
     * GET /matches/donation/{donation_id} - Evaluate and rank candidate NGOs with 7-factor explainability
     */
    evaluateForDonation: (
      token: string,
      donationId: number,
      params?: { min_score?: number; limit?: number; persist_offers?: boolean }
    ) => {
      const q = new URLSearchParams();
      if (params?.min_score !== undefined) q.append("min_score", params.min_score.toString());
      if (params?.limit !== undefined) q.append("limit", params.limit.toString());
      if (params?.persist_offers !== undefined)
        q.append("persist_offers", params.persist_offers.toString());
      const qs = q.toString() ? `?${q.toString()}` : "";
      return request<DonationMatchResponse>(`/matches/donation/${donationId}${qs}`, { token });
    },

    /** POST /matches/donation/{donation_id}/offers - Generate persistent offers for top NGOs */
    createOffers: (token: string, donationId: number, payload?: BatchOfferRequest) =>
      request<MatchOfferResponse[]>(`/matches/donation/${donationId}/offers`, {
        method: "POST",
        token,
        body: payload || {},
      }),

    /** GET /matches/pending - View pending match offers for authenticated NGO */
    getPendingOffers: (token: string, ngoId?: number) => {
      const q = new URLSearchParams();
      if (ngoId) q.append("ngo_id", ngoId.toString());
      const qs = q.toString() ? `?${q.toString()}` : "";
      return request<MatchOfferResponse[]>(`/matches/pending${qs}`, { token });
    },

    /** POST /matches/{match_id}/accept - NGO accepts a pending match offer */
    acceptOffer: (token: string, matchId: number) =>
      request<MatchActionResponse>(`/matches/${matchId}/accept`, {
        method: "POST",
        token,
      }),

    /** POST /matches/{match_id}/reject - NGO declines a pending match offer */
    rejectOffer: (token: string, matchId: number) =>
      request<MatchActionResponse>(`/matches/${matchId}/reject`, {
        method: "POST",
        token,
      }),
  },

  // ---------------- Demand Forecasting ----------------
  forecasts: {
    /** GET /forecasts/aggregate - Network-wide aggregated demand by food category */
    getAggregate: (token: string, days = 7) =>
      request<AggregateForecastResponse>(`/forecasts/aggregate?days=${days}`, { token }),

    /** GET /forecasts/ngo/{ngo_id} - NGO-specific 7-day demand forecast (requires authorized NGO) */
    getForNGO: (token: string, ngoId: number, days = 7) =>
      request<NGOForecastResponse>(`/forecasts/ngo/${ngoId}?days=${days}`, { token }),

    /** GET /forecasts/evaluation - Accuracy benchmarks (MAE, RMSE, R2) and operational readiness */
    getEvaluation: (token: string) =>
      request<ModelEvaluationResponse>("/forecasts/evaluation", { token }),
  },
};
