import Link from "next/link";
import {
  Utensils,
  HeartHandshake,
  BarChart3,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default function HomePage() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-emerald-50/50 via-white to-slate-50 py-20 sm:py-28 lg:py-32 border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-100/70 border border-emerald-200 text-emerald-800 text-xs font-semibold uppercase tracking-wider mb-8">
            <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
            AI-Driven Food Redistribution &amp; Demand Forecasting
          </div>

          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-slate-900 max-w-4xl mx-auto leading-tight sm:leading-tight">
            Connecting Surplus Food to{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-600 to-teal-500">
              Communities in Need
            </span>
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed">
            <strong className="text-slate-800 font-semibold">SmartBite</strong> pairs restaurants, caterers, and bakeries with verified NGOs using transparent AI matching and 7-day nutritional demand projections.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link href="/sign-up" className="w-full sm:w-auto">
              <Button size="lg" className="w-full sm:w-auto shadow-lg shadow-emerald-600/20 text-base">
                Join as Food Donor <ArrowRight className="h-4 w-4 ml-1.5" />
              </Button>
            </Link>
            <Link href="/sign-up" className="w-full sm:w-auto">
              <Button variant="secondary" size="lg" className="w-full sm:w-auto text-base">
                Join as NGO / Shelter
              </Button>
            </Link>
            <Link href="/forecasts" className="w-full sm:w-auto">
              <Button variant="outline" size="lg" className="w-full sm:w-auto text-base">
                <BarChart3 className="h-4 w-4 mr-2 text-emerald-600" />
                Demand Forecasts
              </Button>
            </Link>
          </div>

          {/* Quick Metrics */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-6 max-w-4xl mx-auto text-left">
            <div className="p-4 rounded-xl bg-white border border-slate-200/70 shadow-xs">
              <p className="text-xs font-medium text-slate-500">Matching Engine</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">Multi-Factor</p>
              <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Distance &amp; Diet Fit
              </p>
            </div>
            <div className="p-4 rounded-xl bg-white border border-slate-200/70 shadow-xs">
              <p className="text-xs font-medium text-slate-500">Predictive Horizon</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">7 Days</p>
              <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                <TrendingUp className="h-3 w-3" /> Demand Projections
              </p>
            </div>
            <div className="p-4 rounded-xl bg-white border border-slate-200/70 shadow-xs">
              <p className="text-xs font-medium text-slate-500">Security &amp; Auth</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">Clerk Core</p>
              <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                <ShieldCheck className="h-3 w-3" /> Verified RBAC
              </p>
            </div>
            <div className="p-4 rounded-xl bg-white border border-slate-200/70 shadow-xs">
              <p className="text-xs font-medium text-slate-500">Zero Food Waste</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">Target 0%</p>
              <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                <Clock className="h-3 w-3" /> Real-Time Pickup
              </p>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 text-center mt-3">
            * Illustrative benchmark indicators modeled across prototype AI test scenarios and verified community records.
          </p>
        </div>
      </section>

      {/* 3-Step Matching Process */}
      <section className="py-16 bg-slate-50 border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-xs font-bold uppercase tracking-wider text-emerald-600 mb-2">
              Transparent Matching
            </h2>
            <h3 className="text-2xl sm:text-3xl font-bold text-slate-900">
              The 3-Step SmartBite Rescue Workflow
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 font-bold text-emerald-700">
                1
              </div>
              <h4 className="text-base font-bold text-slate-900">1. List Surplus Batch</h4>
              <p className="text-sm text-slate-600">
                Restaurants enter food category, portion count, and consumption window (e.g. 6 hours).
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 font-bold text-emerald-700">
                2
              </div>
              <h4 className="text-base font-bold text-slate-900">2. Explainable AI Match</h4>
              <p className="text-sm text-slate-600">
                The engine evaluates road distance, beneficiary dietary fit, and storage capacity to rank recipient NGOs.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 font-bold text-emerald-700">
                3
              </div>
              <h4 className="text-base font-bold text-slate-900">3. One-Click Rescue</h4>
              <p className="text-sm text-slate-600">
                Receiving shelters review the batch with complete transparency and accept it for immediate pickup.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillar Grid */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-xs font-bold uppercase tracking-wider text-emerald-600 mb-3">
              Platform Architecture
            </h2>
            <h3 className="text-3xl sm:text-4xl font-bold text-slate-900 tracking-tight">
              An End-to-End AI Infrastructure for Food Rescue
            </h3>
            <p className="mt-4 text-slate-600">
              Designed from the ground up to prevent logistical delays, eliminate food waste, and deliver nutritious surplus directly to verified community kitchens.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <Card className="hover:border-emerald-200 transition-all hover:shadow-md">
              <CardHeader>
                <div className="h-12 w-12 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-600 mb-4">
                  <Utensils className="h-6 w-6" />
                </div>
                <CardTitle>For Food Donors</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-slate-600 text-sm">
                <p>
                  Post surplus batches in seconds with food type, portion counts, and prep/expiry timestamps.
                </p>
                <ul className="space-y-2 pt-2 border-t border-slate-100">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    Instant candidate NGO matching
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    Explainable AI match scores &amp; reasoning
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    Real-time acceptance notifications
                  </li>
                </ul>
              </CardContent>
            </Card>

            <Card className="hover:border-teal-200 transition-all hover:shadow-md">
              <CardHeader>
                <div className="h-12 w-12 rounded-xl bg-teal-100 flex items-center justify-center text-teal-600 mb-4">
                  <HeartHandshake className="h-6 w-6" />
                </div>
                <CardTitle>For NGOs &amp; Shelters</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-slate-600 text-sm">
                <p>
                  Receive high-compatibility match offers tailored directly to your beneficiary count and dietary needs.
                </p>
                <ul className="space-y-2 pt-2 border-t border-slate-100">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-teal-600 shrink-0" />
                    One-click offer acceptance or refusal
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-teal-600 shrink-0" />
                    Clear pickup coordinates and logistics
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-teal-600 shrink-0" />
                    Capacity safeguards preventing overflow
                  </li>
                </ul>
              </CardContent>
            </Card>

            <Card className="hover:border-sky-200 transition-all hover:shadow-md">
              <CardHeader>
                <div className="h-12 w-12 rounded-xl bg-sky-100 flex items-center justify-center text-sky-600 mb-4">
                  <BarChart3 className="h-6 w-6" />
                </div>
                <CardTitle>Predictive Forecasting</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-slate-600 text-sm">
                <p>
                  Transparent machine learning projections compute nutritional demand over 1, 3, 7, 14, and 30 day horizons.
                </p>
                <ul className="space-y-2 pt-2 border-t border-slate-100">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-sky-600 shrink-0" />
                    Nutritional category taxonomy
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-sky-600 shrink-0" />
                    Confidence metrics and transparent notes
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-sky-600 shrink-0" />
                    MAE and RMSE evaluation benchmarks
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Call to action */}
      <section className="bg-slate-900 text-white py-16">
        <div className="max-w-5xl mx-auto px-4 text-center">
          <Badge variant="success" className="mb-4 bg-emerald-950 text-emerald-400 border-emerald-800">
            Join the SmartBite Network
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            Ready to Rescue Food and Feed Your Community?
          </h2>
          <p className="mt-4 text-slate-300 max-w-xl mx-auto text-base">
            Whether you run a kitchen with surplus meals or manage a community food bank, SmartBite makes matching instant, transparent, and dependable.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row justify-center gap-4">
            <Link href="/sign-up">
              <Button size="lg" className="w-full sm:w-auto bg-emerald-500 hover:bg-emerald-600 text-white">
                Create Free Account
              </Button>
            </Link>
            <Link href="/forecasts">
              <Button variant="outline" size="lg" className="w-full sm:w-auto bg-transparent text-white border-slate-700 hover:bg-slate-800">
                Explore Projections
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
