"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import {
  HeartHandshake,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  AlertCircle,
  Users,
  Shield,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatTimeRemaining } from "@/lib/utils";
import type { MatchOfferResponse, NGO } from "@/lib/types";

export default function NGODashboardPage() {
  const { getToken, isLoaded } = useAuth();

  const [ngoProfile, setNgoProfile] = useState<NGO | null>(null);
  const [pendingOffers, setPendingOffers] = useState<MatchOfferResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    if (!isLoaded) return;
    try {
      const token = await getToken();
      setError(null);
      if (!token) throw new Error("Authentication token not available");

      // Verify onboarding & role
      const authMe = await api.auth.getMe(token);
      if (!authMe.is_onboarded || authMe.role !== "ngo") {
        setError("You have not completed NGO onboarding yet. Please register your NGO profile.");
        setLoading(false);
        return;
      }

      setNgoProfile(authMe.ngo || null);
      const ngoId = authMe.ngo?.id;

      // Fetch pending match offers for this NGO
      const offers = await api.matches.getPendingOffers(token, ngoId);
      setPendingOffers(offers);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load NGO dashboard data. Please check connection.");
      }
    } finally {
      setLoading(false);
    }
  }, [isLoaded, getToken]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDashboardData();
  }, [fetchDashboardData]);

  const handleAcceptOffer = async (offerId: number) => {
    setActionLoadingId(offerId);
    setActionSuccessMessage(null);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await api.matches.acceptOffer(token, offerId);
      setActionSuccessMessage(res.message || "Match offer accepted! Scheduled for pickup.");
      // Refresh pending offers
      setPendingOffers((prev) => prev.filter((o) => o.id !== offerId));
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to accept donation offer.");
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRejectOffer = async (offerId: number) => {
    setActionLoadingId(offerId);
    setActionSuccessMessage(null);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await api.matches.rejectOffer(token, offerId);
      setActionSuccessMessage(res.message || "Offer declined. Donation will be offered to the next candidate NGO.");
      setPendingOffers((prev) => prev.filter((o) => o.id !== offerId));
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to decline offer.");
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 py-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            NGO Community Portal
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Review incoming donation offers, verify food suitability, and accept surplus batches.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              fetchDashboardData();
            }}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Offers
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {actionSuccessMessage && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
          <span>{actionSuccessMessage}</span>
        </div>
      )}

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

      {/* NGO Profile Highlights */}
      {ngoProfile && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="p-4 rounded-xl bg-white border border-slate-200/80 shadow-2xs flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-600">
              <HeartHandshake className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Organization</p>
              <p className="text-sm font-bold text-slate-900">{ngoProfile.name}</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-white border border-slate-200/80 shadow-2xs flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-teal-100 flex items-center justify-center text-teal-600">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Beneficiaries Served</p>
              <p className="text-sm font-bold text-slate-900">
                {ngoProfile.beneficiary_count} individuals / day
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-white border border-slate-200/80 shadow-2xs flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-sky-100 flex items-center justify-center text-sky-600">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-slate-500">Dietary Scope</p>
              <p className="text-sm font-bold text-slate-900 truncate max-w-[200px]">
                {ngoProfile.food_requirements || "All Categories"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Pending Offers Feed */}
      {loading ? (
        <div className="p-16 text-center flex flex-col items-center justify-center bg-white rounded-2xl border border-slate-200">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
          <p className="text-sm text-slate-500 font-medium">Checking incoming food matches...</p>
        </div>
      ) : pendingOffers.length === 0 ? (
        <Card className="text-center py-16 px-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50 text-teal-600 mb-4">
            <Sparkles className="h-7 w-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">No pending offers right now</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
            When donors post surplus food within your delivery radius and matching your nutritional needs, offers will appear here for one-click acceptance.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Pending Offers ({pendingOffers.length})
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {pendingOffers.map((offer) => {
              const timeInfo = offer.available_until
                ? formatTimeRemaining(offer.available_until)
                : { text: "No expiry specified", isUrgent: false };
              const isActionRunning = actionLoadingId === offer.id;

              return (
                <Card key={offer.id} className="border-emerald-100 hover:border-emerald-300 transition-all flex flex-col justify-between">
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div>
                        <div className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full mb-1">
                          <Sparkles className="h-3 w-3" /> Match Score: {Math.round(offer.match_score)}%
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 leading-snug">
                          {offer.food_name || "Surplus Food Batch"}
                        </h3>
                        {offer.restaurant_name && (
                          <p className="text-xs text-slate-500 mt-0.5">
                            From: {offer.restaurant_name}
                          </p>
                        )}
                      </div>
                      <Badge variant="warning">Action Needed</Badge>
                    </div>

                    <div className="space-y-2 text-sm text-slate-600 mb-4">
                      {offer.food_category && (
                        <div className="flex items-center justify-between text-xs py-1 px-2.5 rounded-lg bg-slate-50 border border-slate-100">
                          <span className="font-medium text-slate-500">Category:</span>
                          <span className="font-semibold text-slate-800">{offer.food_category}</span>
                        </div>
                      )}
                      {offer.quantity !== null && offer.quantity !== undefined && (
                        <div className="flex items-center justify-between text-xs py-1 px-2.5 rounded-lg bg-slate-50 border border-slate-100">
                          <span className="font-medium text-slate-500">Portions / Volume:</span>
                          <span className="font-semibold text-slate-800">
                            {offer.quantity} kg
                          </span>
                        </div>
                      )}
                      {offer.available_until && (
                        <div className="flex items-center gap-1.5 text-xs">
                          <Clock className={`h-3.5 w-3.5 ${timeInfo.isUrgent ? "text-rose-500" : "text-amber-500"}`} />
                          <span className={timeInfo.isUrgent ? "text-rose-600 font-semibold" : "text-slate-600"}>
                            {timeInfo.text} (Expiry: {formatDate(offer.available_until)})
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRejectOffer(offer.id)}
                      disabled={isActionRunning}
                    >
                      <XCircle className="h-4 w-4 mr-1 text-slate-500" />
                      Decline
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleAcceptOffer(offer.id)}
                      isLoading={isActionRunning}
                    >
                      <CheckCircle2 className="h-4 w-4 mr-1 text-white" />
                      Accept Donation
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
