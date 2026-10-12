"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import {
  ArrowLeft,
  UtensilsCrossed,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";

const CATEGORIES = [
  "Cooked Meals",
  "Bakery",
  "Fresh Produce",
  "Dairy",
  "Packaged Goods",
  "Catering Surplus",
];

const UNITS = ["portions", "kg", "boxes", "liters", "units"];

export default function NewDonationPage() {
  const { getToken } = useAuth();
  const router = useRouter();

  const [formData, setFormData] = useState({
    title: "",
    food_type: "Cooked Meals",
    quantity: 25,
    unit: "portions",
    expiry_hours: 6,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const token = await getToken();
      if (!token) throw new Error("Authentication token unavailable");

      // Verify restaurant profile
      const authMe = await api.auth.getMe(token);
      if (!authMe.is_onboarded || !authMe.restaurant) {
        throw new Error("You must complete restaurant onboarding before creating donations.");
      }

      const restId = authMe.restaurant.id;
      const now = new Date();
      const availableUntil = new Date(now.getTime() + formData.expiry_hours * 3600 * 1000);

      await api.donations.create(token, {
        restaurant_id: restId,
        food_name: formData.title,
        food_category: formData.food_type,
        quantity: Number(formData.quantity),
        prepared_at: now.toISOString(),
        available_until: availableUntil.toISOString(),
        storage_method: "ambient",
        pickup_available: true,
      });

      setSuccess(true);
      setTimeout(() => {
        router.push("/dashboard/restaurant");
      }, 1500);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Failed to create surplus donation listing.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] py-12 px-4 sm:px-6 lg:px-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <Link
          href="/dashboard/restaurant"
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-emerald-600 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Dashboard
        </Link>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-600">
              <UtensilsCrossed className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>List Surplus Food for Rescue</CardTitle>
              <CardDescription>
                Provide details about the prepared food batch. SmartBite AI will immediately calculate distance and compatibility for local shelters.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {success ? (
            <div className="py-12 text-center space-y-3">
              <div className="mx-auto h-12 w-12 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Surplus Batch Listed!</h3>
              <p className="text-sm text-slate-500">
                AI matching engine is evaluating nearby candidate NGOs. Redirecting to dashboard...
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {errorMessage && (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-sm text-rose-700">
                  {errorMessage}
                </div>
              )}

              <Input
                label="Food Description / Title"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g. 40 Packaged Bento Boxes with Teriyaki Chicken &amp; Rice"
                helperText="Be specific so receiving NGOs can understand dietary composition"
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Select
                  label="Nutritional Category"
                  value={formData.food_type}
                  onChange={(e) => setFormData({ ...formData, food_type: e.target.value })}
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </Select>

                <div className="grid grid-cols-2 gap-2">
                  <Input
                    label="Quantity"
                    type="number"
                    min={1}
                    required
                    value={formData.quantity}
                    onChange={(e) =>
                      setFormData({ ...formData, quantity: parseInt(e.target.value) || 1 })
                    }
                  />
                  <Select
                    label="Unit"
                    value={formData.unit}
                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  >
                    {UNITS.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Safe Consumption Window: {formData.expiry_hours} hours from now
                </label>
                <input
                  type="range"
                  min={1}
                  max={48}
                  step={1}
                  value={formData.expiry_hours}
                  onChange={(e) =>
                    setFormData({ ...formData, expiry_hours: parseInt(e.target.value) || 6 })
                  }
                  className="w-full accent-emerald-600 cursor-pointer"
                />
                <div className="flex justify-between text-xs text-slate-400 mt-1">
                  <span>1 Hour (Immediate pickup)</span>
                  <span>12 Hours</span>
                  <span>24 Hours</span>
                  <span>48 Hours</span>
                </div>
              </div>

              <div className="pt-4 flex items-center justify-between border-t border-slate-100">
                <div className="text-xs text-slate-500 flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-emerald-600" />
                  Instant notification to compatible NGOs
                </div>
                <Button type="submit" size="lg" isLoading={isSubmitting}>
                  Post &amp; Match Now
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
