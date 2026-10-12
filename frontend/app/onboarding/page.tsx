"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth, useUser } from "@clerk/nextjs";
import { Building2, HeartHandshake, ArrowRight, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";

export default function OnboardingPage() {
  const { getToken, isLoaded: isAuthLoaded } = useAuth();
  const { user } = useUser();
  const router = useRouter();

  const [checkingState, setCheckingState] = useState(true);
  const [selectedRole, setSelectedRole] = useState<"restaurant" | "ngo">("restaurant");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Derived name from Clerk account
  const clerkName = user?.fullName || user?.firstName || "";

  // Restaurant form fields
  const [restForm, setRestForm] = useState({
    name: "",
    restaurant_name: "",
    address: "",
    latitude: 6.45,
    longitude: 3.40,
    phone: "",
  });

  // NGO form fields
  const [ngoForm, setNgoForm] = useState({
    name: "",
    ngo_name: "",
    address: "",
    latitude: 6.46,
    longitude: 3.41,
    beneficiary_count: 50,
    food_requirements: "Cooked Meals, Bakery, Fresh Produce",
    capacity: 200,
    pickup_available: true,
  });

  // Check if user has already onboarded
  useEffect(() => {
    async function checkOnboarding() {
      if (!isAuthLoaded) return;
      try {
        const token = await getToken();
        if (token) {
          const authData = await api.auth.getMe(token);
          if (authData.is_onboarded) {
            if (authData.role === "restaurant") {
              router.push("/dashboard/restaurant");
              return;
            } else if (authData.role === "ngo") {
              router.push("/dashboard/ngo");
              return;
            }
          }
        }
      } catch {
        // Not yet onboarded or new user
      } finally {
        setCheckingState(false);
      }
    }

    checkOnboarding();
  }, [isAuthLoaded, getToken, router]);

  const handleRestaurantSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const token = await getToken();
      if (!token) throw new Error("Authentication token unavailable");

      await api.auth.onboardRestaurant(token, {
        name: restForm.name.trim() || clerkName || "Representative",
        restaurant_name: restForm.restaurant_name,
        address: restForm.address,
        latitude: Number(restForm.latitude),
        longitude: Number(restForm.longitude),
        phone: restForm.phone || undefined,
      });

      router.push("/dashboard/restaurant");
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("An unexpected error occurred during onboarding.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNGOSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const token = await getToken();
      if (!token) throw new Error("Authentication token unavailable");

      await api.auth.onboardNGO(token, {
        name: ngoForm.name.trim() || clerkName || "Representative",
        ngo_name: ngoForm.ngo_name,
        address: ngoForm.address,
        latitude: Number(ngoForm.latitude),
        longitude: Number(ngoForm.longitude),
        beneficiary_count: Number(ngoForm.beneficiary_count),
        food_requirements: ngoForm.food_requirements,
        capacity: Number(ngoForm.capacity),
        pickup_available: ngoForm.pickup_available,
      });

      router.push("/dashboard/ngo");
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("An unexpected error occurred during onboarding.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (checkingState) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center">
        <div className="text-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mx-auto" />
          <p className="text-sm text-slate-500 font-medium">Verifying SmartBite profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-8rem)] py-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
      <div className="text-center max-w-2xl mx-auto mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Welcome to Smart<span className="text-emerald-600">Bite</span>
        </h1>
        <p className="mt-2 text-slate-600">
          Complete your organization profile to connect with surplus donors or verified community beneficiaries.
        </p>
      </div>

      {/* Role Selection Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <button
          type="button"
          onClick={() => setSelectedRole("restaurant")}
          className={`p-6 rounded-2xl border text-left transition-all cursor-pointer ${
            selectedRole === "restaurant"
              ? "border-emerald-600 bg-emerald-50/50 shadow-sm ring-2 ring-emerald-600/20"
              : "border-slate-200 bg-white hover:border-slate-300"
          }`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-white">
              <Building2 className="h-6 w-6" />
            </div>
            {selectedRole === "restaurant" && (
              <CheckCircle2 className="h-6 w-6 text-emerald-600" />
            )}
          </div>
          <h3 className="text-lg font-bold text-slate-900">I am a Food Donor</h3>
          <p className="mt-1 text-sm text-slate-600">
            Restaurants, bakeries, caterers, or grocery stores with surplus food looking to reduce waste.
          </p>
        </button>

        <button
          type="button"
          onClick={() => setSelectedRole("ngo")}
          className={`p-6 rounded-2xl border text-left transition-all cursor-pointer ${
            selectedRole === "ngo"
              ? "border-emerald-600 bg-emerald-50/50 shadow-sm ring-2 ring-emerald-600/20"
              : "border-slate-200 bg-white hover:border-slate-300"
          }`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-white">
              <HeartHandshake className="h-6 w-6" />
            </div>
            {selectedRole === "ngo" && (
              <CheckCircle2 className="h-6 w-6 text-emerald-600" />
            )}
          </div>
          <h3 className="text-lg font-bold text-slate-900">I am an NGO / Food Bank</h3>
          <p className="mt-1 text-sm text-slate-600">
            Shelters, community kitchens, or charities distributing food to individuals in need.
          </p>
        </button>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-sm text-rose-700">
          {errorMessage}
        </div>
      )}

      {/* Form Container */}
      <Card>
        <CardHeader>
          <CardTitle>
            {selectedRole === "restaurant"
              ? "Register Your Food Business"
              : "Register Your NGO / Shelter"}
          </CardTitle>
          <CardDescription>
            {selectedRole === "restaurant"
              ? "Provide your location details to enable accurate distance calculation for donation matching."
              : "Specify your beneficiary capacity and dietary requirements for explainable AI matching."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {selectedRole === "restaurant" ? (
            <form onSubmit={handleRestaurantSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Representative Full Name"
                  required
                  value={restForm.name || clerkName}
                  onChange={(e) => setRestForm({ ...restForm, name: e.target.value })}
                  placeholder={clerkName || "e.g. Chef Luigi"}
                />
                <Input
                  label="Restaurant / Store Name"
                  required
                  value={restForm.restaurant_name}
                  onChange={(e) => setRestForm({ ...restForm, restaurant_name: e.target.value })}
                  placeholder="e.g. Green Garden Bistro"
                />
              </div>

              <Input
                label="Street Address"
                required
                value={restForm.address}
                onChange={(e) => setRestForm({ ...restForm, address: e.target.value })}
                placeholder="e.g. 44 Adeola Odeku Street, Victoria Island, Lagos"
              />

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Input
                  label="Latitude"
                  type="number"
                  step="any"
                  required
                  value={restForm.latitude}
                  onChange={(e) => setRestForm({ ...restForm, latitude: parseFloat(e.target.value) || 0 })}
                />
                <Input
                  label="Longitude"
                  type="number"
                  step="any"
                  required
                  value={restForm.longitude}
                  onChange={(e) => setRestForm({ ...restForm, longitude: parseFloat(e.target.value) || 0 })}
                />
                <Input
                  label="Contact Phone (Optional)"
                  type="tel"
                  value={restForm.phone}
                  onChange={(e) => setRestForm({ ...restForm, phone: e.target.value })}
                  placeholder="+234 800 000 0000"
                />
              </div>

              <div className="pt-4 flex justify-end">
                <Button type="submit" size="lg" isLoading={isSubmitting}>
                  Complete Restaurant Profile <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleNGOSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Representative Full Name"
                  required
                  value={ngoForm.name || clerkName}
                  onChange={(e) => setNgoForm({ ...ngoForm, name: e.target.value })}
                  placeholder={clerkName || "e.g. Sarah Jenkins"}
                />
                <Input
                  label="NGO / Organization Name"
                  required
                  value={ngoForm.ngo_name}
                  onChange={(e) => setNgoForm({ ...ngoForm, ngo_name: e.target.value })}
                  placeholder="e.g. Community Hope Kitchen"
                />
              </div>

              <Input
                label="Facility Address"
                required
                value={ngoForm.address}
                onChange={(e) => setNgoForm({ ...ngoForm, address: e.target.value })}
                placeholder="e.g. 12 Broad Street, Lagos Island"
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Daily Beneficiaries Served"
                  type="number"
                  required
                  min={1}
                  value={ngoForm.beneficiary_count}
                  onChange={(e) => setNgoForm({ ...ngoForm, beneficiary_count: parseInt(e.target.value) || 1 })}
                />
                <Input
                  label="Storage / Distribution Capacity (kg)"
                  type="number"
                  required
                  min={1}
                  value={ngoForm.capacity}
                  onChange={(e) => setNgoForm({ ...ngoForm, capacity: parseInt(e.target.value) || 1 })}
                />
              </div>

              <Input
                label="Dietary &amp; Food Requirements"
                helperText="Comma-separated categories your beneficiaries need (e.g. Cooked Meals, Bakery, Fresh Produce)"
                required
                value={ngoForm.food_requirements}
                onChange={(e) => setNgoForm({ ...ngoForm, food_requirements: e.target.value })}
                placeholder="Cooked Meals, Dairy, Bakery"
              />

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="pickup"
                  checked={ngoForm.pickup_available}
                  onChange={(e) => setNgoForm({ ...ngoForm, pickup_available: e.target.checked })}
                  className="h-4 w-4 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300"
                />
                <label htmlFor="pickup" className="text-sm font-medium text-slate-700">
                  We have dedicated staff or vehicles to handle on-site pickup from donors
                </label>
              </div>

              <div className="pt-4 flex justify-end">
                <Button type="submit" size="lg" isLoading={isSubmitting}>
                  Complete NGO Profile <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
