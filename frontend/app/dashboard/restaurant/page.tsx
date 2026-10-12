"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import {
  Utensils,
  Plus,
  Sparkles,
  MapPin,
  Clock,
  Loader2,
  RefreshCw,
  AlertCircle,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatTimeRemaining } from "@/lib/utils";
import type { FoodDonation, NGOMatchResult } from "@/lib/types";

export default function RestaurantDashboardPage() {
  const { getToken, isLoaded } = useAuth();

  const [donations, setDonations] = useState<FoodDonation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected donation for match recommendation drawer/modal
  const [selectedDonation, setSelectedDonation] = useState<FoodDonation | null>(null);
  const [matches, setMatches] = useState<NGOMatchResult[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);

  const fetchDonations = useCallback(async () => {
    if (!isLoaded) return;
    try {
      const token = await getToken();
      setError(null);
      if (!token) throw new Error("Authentication token not available");

      // Verify onboarding first
      const authMe = await api.auth.getMe(token);
      if (!authMe.is_onboarded || authMe.role !== "restaurant") {
        setError("You have not completed restaurant onboarding yet. Please onboard first.");
        setLoading(false);
        return;
      }

      const restId = authMe.restaurant?.id;
      const data = await api.donations.list(token, { restaurant_id: restId });
      setDonations(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load restaurant donations. Please check backend connection.");
      }
    } finally {
      setLoading(false);
    }
  }, [isLoaded, getToken]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDonations();
  }, [fetchDonations]);

  const viewMatches = async (donation: FoodDonation) => {
    setSelectedDonation(donation);
    setLoadingMatches(true);
    setMatches([]);
    try {
      const token = await getToken();
      if (!token) return;
      const results = await api.matches.evaluateForDonation(token, donation.id);
      setMatches(results.matches);
    } catch (err) {
      console.error("Failed to load matches", err);
    } finally {
      setLoadingMatches(false);
    }
  };

  const getStatusBadge = (status: FoodDonation["status"]) => {
    switch (status) {
      case "available":
        return <Badge variant="info">Available</Badge>;
      case "matched":
        return <Badge variant="warning">Matched (Pending)</Badge>;
      case "accepted":
        return <Badge variant="success">Accepted</Badge>;
      case "completed":
        return <Badge variant="neutral">Completed</Badge>;
      case "expired":
        return <Badge variant="danger">Expired</Badge>;
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 py-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Restaurant Donation Portal
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Monitor active surplus batches, review AI match recommendations, and coordinate rescues.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              fetchDonations();
            }}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Link href="/donations/new">
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1.5" /> Post Surplus Food
            </Button>
          </Link>
        </div>
      </div>

      {/* Error notification */}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <span>{error}</span>
          </div>
          <Link href="/onboarding" className="font-semibold underline text-amber-900 ml-4">
            Go to Onboarding
          </Link>
        </div>
      )}

      {/* Main Content */}
      {loading ? (
        <div className="p-16 text-center flex flex-col items-center justify-center bg-white rounded-2xl border border-slate-200">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
          <p className="text-sm text-slate-500 font-medium">Loading restaurant donations...</p>
        </div>
      ) : donations.length === 0 ? (
        <Card className="text-center py-16 px-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 mb-4">
            <Utensils className="h-7 w-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">No surplus donations posted yet</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mt-1 mb-6">
            Whenever your kitchen has extra prepared meals, produce, or bakery items, post them here to immediately match with verified local shelters.
          </p>
          <Link href="/donations/new">
            <Button>
              <Plus className="h-4 w-4 mr-1.5" /> Create Your First Donation
            </Button>
          </Link>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {donations.map((item) => {
            const timeInfo = formatTimeRemaining(item.available_until);
            return (
              <Card key={item.id} className="flex flex-col justify-between hover:shadow-md transition-shadow">
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <h3 className="font-bold text-slate-900 text-base leading-snug">
                      {item.food_name}
                    </h3>
                    {getStatusBadge(item.status)}
                  </div>

                  <div className="space-y-2 text-sm text-slate-600 mb-4">
                    <div className="flex items-center justify-between text-xs py-1 px-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="font-medium text-slate-500">Category:</span>
                      <span className="font-semibold text-slate-800">{item.food_category}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-1 px-2.5 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="font-medium text-slate-500">Quantity:</span>
                      <span className="font-semibold text-slate-800">
                        {item.quantity} kg
                      </span>
                    </div>
                    {item.prepared_at && (
                      <div className="flex items-center gap-1.5 text-xs text-slate-500">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        <span>Prep: {formatDate(item.prepared_at)}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 text-xs">
                      <Clock className={`h-3.5 w-3.5 ${timeInfo.isUrgent ? "text-rose-500" : "text-amber-500"}`} />
                      <span className={timeInfo.isUrgent ? "text-rose-600 font-semibold" : "text-slate-600"}>
                        {timeInfo.text} (Expiry: {formatDate(item.available_until)})
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-400">ID: #{item.id}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => viewMatches(item)}
                    className="text-xs"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-emerald-600 mr-1" />
                    AI Matches
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* AI Matches Modal / Drawer */}
      {selectedDonation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-600">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-lg">
                    AI Match Recommendations
                  </h3>
                  <p className="text-xs text-slate-500">
                    Matches for: &ldquo;{selectedDonation.food_name}&rdquo; ({selectedDonation.quantity} kg)
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedDonation(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="py-4">
              {loadingMatches ? (
                <div className="p-10 text-center flex flex-col items-center">
                  <Loader2 className="h-6 w-6 animate-spin text-emerald-600 mb-2" />
                  <p className="text-sm text-slate-500">Computing 7-factor explainable compatibility scores...</p>
                </div>
              ) : matches.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-slate-500">
                    No verified NGOs currently match the distance or dietary criteria for this donation.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {matches.map((m, idx) => (
                    <div
                      key={m.ngo_id}
                      className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-white transition-all space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800">
                              #{idx + 1}
                            </span>
                            <h4 className="font-bold text-slate-900 text-sm">{m.ngo_name}</h4>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-semibold">
                              {m.match_tier}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-slate-400" />
                            {m.distance_km.toFixed(1)} km away &bull; ~{Math.round(m.estimated_people_served)} meals delivered
                          </p>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-extrabold text-emerald-600">
                            {Math.round(m.match_score)}%
                          </span>
                          <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                            Match Score
                          </p>
                        </div>
                      </div>

                      {/* Breakdown badges */}
                      <div className="flex flex-wrap gap-2 text-[11px]">
                        <span className="px-2 py-0.5 rounded-md bg-slate-200/70 text-slate-700">
                          Distance: {Math.round(m.distance_score)}%
                        </span>
                        <span className="px-2 py-0.5 rounded-md bg-slate-200/70 text-slate-700">
                          Diet Compatibility: {Math.round(m.food_compatibility_score)}%
                        </span>
                        <span className="px-2 py-0.5 rounded-md bg-slate-200/70 text-slate-700">
                          Demand Fit: {Math.round(m.demand_score)}%
                        </span>
                        <span className="px-2 py-0.5 rounded-md bg-slate-200/70 text-slate-700">
                          Pickup: {m.pickup_available ? "NGO Collects" : "Donor Transport"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-slate-200 flex justify-end">
              <Button variant="secondary" onClick={() => setSelectedDonation(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
