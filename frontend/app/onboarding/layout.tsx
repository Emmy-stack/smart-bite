"use client";

import React from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}
