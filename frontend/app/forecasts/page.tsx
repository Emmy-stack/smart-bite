"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  BarChart3,
  TrendingUp,
  Users,
  Sparkles,
  ShieldCheck,
  Loader2,
  Layers,
  CheckCircle2,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";
import type { AggregateForecastResponse, ModelEvaluationResponse } from "@/lib/types";

export default function ForecastsPage() {
  const { getToken } = useAuth();

  const [days, setDays] = useState(7);
  const [forecastData, setForecastData] = useState<AggregateForecastResponse | null>(null);
  const [evalData, setEvalData] = useState<ModelEvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"forecast" | "evaluation">("forecast");

  const loadData = useCallback(async (horizon: number) => {
    try {
      const token = await getToken();
      setError(null);
      const [fRes, eRes] = await Promise.all([
        api.forecasts.getAggregate(token || "", horizon),
        api.forecasts.getEvaluation(token || "").catch(() => null),
      ]);
      setForecastData(fRes);
      setEvalData(eRes);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to connect to SmartBite forecasting service.");
      }
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData(days);
  }, [days, loadData]);

  return (
    <div className="min-h-screen bg-slate-50/50 py-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full mb-2">
            <Sparkles className="h-3.5 w-3.5" /> Predictive Demand Intelligence
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            AI-Powered Food Demand Forecasting
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Anticipate community food needs across nutritional categories to proactively prevent shortages and waste.
          </p>
        </div>

        {/* Horizon selector buttons */}
        <div className="flex items-center gap-1 p-1 bg-white rounded-xl border border-slate-200 self-start">
          {[1, 3, 7, 14, 30].map((h) => (
            <button
              key={h}
              onClick={() => {
                setDays(h);
                setLoading(true);
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                days === h
                  ? "bg-emerald-600 text-white shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {h} Days
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 border-b border-slate-200 mb-8">
        <button
          onClick={() => setActiveTab("forecast")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === "forecast"
              ? "border-emerald-600 text-emerald-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <BarChart3 className="h-4 w-4" /> Category Demand Projections
        </button>
        <button
          onClick={() => setActiveTab("evaluation")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === "evaluation"
              ? "border-emerald-600 text-emerald-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <ShieldCheck className="h-4 w-4" /> Model Transparency &amp; Evaluation
        </button>
      </div>

      {loading ? (
        <div className="p-20 text-center flex flex-col items-center justify-center bg-white rounded-2xl border border-slate-200">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
          <p className="text-sm text-slate-600 font-medium">Computing {days}-day nutritional demand projections...</p>
          <p className="text-xs text-slate-400 mt-1">Aggregating beneficiary counts and taxonomy categories</p>
        </div>
      ) : error ? (
        <Card className="p-10 text-center">
          <p className="text-sm text-rose-600 font-medium mb-4">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              loadData(days);
            }}
            className="text-xs font-semibold text-emerald-600 underline"
          >
            Retry Connection
          </button>
        </Card>
      ) : activeTab === "forecast" && forecastData ? (
        <div className="space-y-8">
          {/* Top KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Total Network Demand
                </span>
                <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
                  <TrendingUp className="h-5 w-5" />
                </div>
              </div>
              <p className="text-3xl font-extrabold text-slate-900 mt-2">
                {forecastData.total_network_demand_kg.toLocaleString()}{" "}
                <span className="text-base font-normal text-slate-500">kg</span>
              </p>
              <p className="text-xs text-slate-500 mt-1">Over next {days} days</p>
            </div>

            <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Beneficiaries Supported
                </span>
                <div className="p-2 rounded-xl bg-teal-50 text-teal-600">
                  <Users className="h-5 w-5" />
                </div>
              </div>
              <p className="text-3xl font-extrabold text-slate-900 mt-2">
                {forecastData.total_beneficiaries_served.toLocaleString()}
              </p>
              <p className="text-xs text-slate-500 mt-1">Across {forecastData.active_ngos_count} verified NGOs</p>
            </div>

            <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Categories Modeled
                </span>
                <div className="p-2 rounded-xl bg-sky-50 text-sky-600">
                  <Layers className="h-5 w-5" />
                </div>
              </div>
              <p className="text-3xl font-extrabold text-slate-900 mt-2">
                {forecastData.category_breakdown.length}
              </p>
              <p className="text-xs text-slate-500 mt-1">Standardized nutritional taxonomy</p>
            </div>
          </div>

          {/* Categories Grid */}
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-slate-900">
              Demand by Category ({days}-Day Horizon)
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {forecastData.category_breakdown.map((c) => (
                <Card key={c.food_category} className="hover:shadow-md transition-all">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">{c.food_category}</CardTitle>
                      <Badge variant="success">
                        {c.percentage_of_network_total.toFixed(1)}% Share
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-baseline justify-between py-2 border-y border-slate-100">
                      <span className="text-xs text-slate-500">Projected Demand:</span>
                      <span className="text-xl font-extrabold text-emerald-600">
                        {c.total_estimated_demand_kg.toLocaleString()} kg
                      </span>
                    </div>

                    <div className="flex justify-between text-xs text-slate-500">
                      <span>Daily Network Average:</span>
                      <span className="font-semibold text-slate-700">
                        {c.daily_average_kg.toFixed(1)} kg / day
                      </span>
                    </div>

                    <div className="flex justify-between text-xs text-slate-500">
                      <span>Recipient NGOs:</span>
                      <span className="font-semibold text-slate-700">
                        {c.contributing_ngos_count} organizations
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Methodology Card */}
          <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-900 flex items-start gap-2.5">
            <Sparkles className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Explainable AI Methodology: </span>
              {forecastData.method}. {forecastData.disclaimer}
            </div>
          </div>
        </div>
      ) : activeTab === "evaluation" && evalData ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                Model Transparency &amp; Evaluation Report
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-700">
                <p className="font-semibold text-slate-900 mb-1">Status: {evalData.status.toUpperCase()}</p>
                <p>{evalData.message}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-white border border-slate-200">
                  <span className="text-xs font-semibold text-slate-500">Completed Donations Sample</span>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    {evalData.sample_size_completed_donations}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">Total completed rescue events logged</p>
                </div>
                <div className="p-4 rounded-xl bg-white border border-slate-200">
                  <span className="text-xs font-semibold text-slate-500">Recipient NGOs with History</span>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    {evalData.unique_recipient_ngos}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">Active verified distribution points</p>
                </div>
              </div>

              {evalData.data_collection_requirements && evalData.data_collection_requirements.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Operational Data Readiness Criteria:
                  </h4>
                  <ul className="space-y-1.5 text-xs text-slate-600">
                    {evalData.data_collection_requirements.map((req, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                        {req}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {evalData.metrics_definitions && (
                <div className="p-4 rounded-xl bg-slate-100 text-xs text-slate-600 space-y-1.5">
                  <p className="font-semibold text-slate-800">Metric Definitions:</p>
                  {Object.entries(evalData.metrics_definitions).map(([k, v]) => (
                    <p key={k}>
                      <strong>{k}:</strong> {v}
                    </p>
                  ))}
                  <p className="text-[11px] text-slate-400 pt-1">
                    Evaluated on {formatDate(evalData.evaluation_timestamp)}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function formatDate(dateString: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(dateString));
  } catch {
    return dateString;
  }
}
