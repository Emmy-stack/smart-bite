import React from "react";
import Link from "next/link";
import { Utensils, Heart, Shield, Sparkles } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          {/* Brand col */}
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white">
                <Utensils className="h-4 w-4" />
              </div>
              <span className="text-xl font-bold tracking-tight text-slate-900">
                Smart<span className="text-emerald-600">Bite</span>
              </span>
            </div>
            <p className="text-sm text-slate-500 max-w-sm">
              Empowering food rescue through explainable AI matching and predictive demand forecasting. Connecting surplus food with verified local communities.
            </p>
            <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 w-fit px-3 py-1.5 rounded-full font-medium">
              <Sparkles className="h-3.5 w-3.5" />
              AI Matching &amp; 7-Day Forecasting Active
            </div>
          </div>

          {/* Quick links */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900 mb-4">
              Platform
            </h4>
            <ul className="space-y-2.5 text-sm text-slate-600">
              <li>
                <Link href="/forecasts" className="hover:text-emerald-600 transition-colors">
                  Demand Forecasting
                </Link>
              </li>
              <li>
                <Link href="/dashboard/restaurant" className="hover:text-emerald-600 transition-colors">
                  Restaurant Portal
                </Link>
              </li>
              <li>
                <Link href="/dashboard/ngo" className="hover:text-emerald-600 transition-colors">
                  NGO Network
                </Link>
              </li>
              <li>
                <Link href="/donations/new" className="hover:text-emerald-600 transition-colors">
                  Donate Food
                </Link>
              </li>
            </ul>
          </div>

          {/* Verification & Trust */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900 mb-4">
              Trust &amp; Verification
            </h4>
            <ul className="space-y-2.5 text-sm text-slate-600">
              <li className="flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-emerald-600" />
                Verified NGO Beneficiaries
              </li>
              <li className="flex items-center gap-1.5">
                <Heart className="h-4 w-4 text-emerald-600" />
                Zero Food Waste Mission
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-4">
          <p>© 2026 SmartBite Platform. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <span>FastAPI + Next.js</span>
            <span>Clerk Authentication</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
