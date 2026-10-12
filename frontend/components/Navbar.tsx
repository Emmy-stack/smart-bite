"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth, UserButton } from "@clerk/nextjs";
import { Utensils, BarChart3, Menu, X, ArrowRight, HeartHandshake } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function Navbar() {
  const { isLoaded, isSignedIn } = useAuth();
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { name: "Demand Forecasts", href: "/forecasts", icon: BarChart3 },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-md shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            <Utensils className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold tracking-tight text-slate-900">
            Smart<span className="text-emerald-600">Bite</span>
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-6">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "text-emerald-600"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Icon className="h-4 w-4" />
                {link.name}
              </Link>
            );
          })}

          {isLoaded && isSignedIn && (
            <>
              <Link
                href="/onboarding"
                className={`text-sm font-medium transition-colors ${
                  pathname === "/onboarding"
                    ? "text-emerald-600"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Onboarding
              </Link>
              <Link
                href="/dashboard/restaurant"
                className={`text-sm font-medium transition-colors ${
                  pathname.startsWith("/dashboard")
                    ? "text-emerald-600"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Dashboard
              </Link>
            </>
          )}
        </nav>

        {/* Auth CTA & Profile */}
        <div className="hidden md:flex items-center gap-3">
          {isLoaded ? (
            isSignedIn ? (
              <div className="flex items-center gap-4">
                <Link href="/donations/new">
                  <Button size="sm" className="shadow-xs">
                    <HeartHandshake className="h-4 w-4 mr-1" />
                    New Donation
                  </Button>
                </Link>
                <UserButton />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link href="/sign-in">
                  <Button variant="ghost" size="sm">
                    Sign In
                  </Button>
                </Link>
                <Link href="/sign-up">
                  <Button size="sm">
                    Get Started <ArrowRight className="h-3.5 w-3.5 ml-1" />
                  </Button>
                </Link>
              </div>
            )
          ) : (
            <div className="h-9 w-20 bg-slate-100 animate-pulse rounded-lg" />
          )}
        </div>

        {/* Mobile menu toggle */}
        <div className="flex md:hidden items-center gap-2">
          {isLoaded && isSignedIn && <UserButton />}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 focus:outline-none"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-slate-200 bg-white px-4 pt-3 pb-6 space-y-3">
          <Link
            href="/forecasts"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-2 py-2 text-sm font-medium text-slate-700 hover:text-emerald-600"
          >
            <BarChart3 className="h-4 w-4 text-emerald-600" />
            Demand Forecasts
          </Link>
          {isLoaded && isSignedIn ? (
            <>
              <Link
                href="/dashboard/restaurant"
                onClick={() => setMobileMenuOpen(false)}
                className="block py-2 text-sm font-medium text-slate-700 hover:text-emerald-600"
              >
                Restaurant Dashboard
              </Link>
              <Link
                href="/dashboard/ngo"
                onClick={() => setMobileMenuOpen(false)}
                className="block py-2 text-sm font-medium text-slate-700 hover:text-emerald-600"
              >
                NGO Dashboard
              </Link>
              <Link
                href="/donations/new"
                onClick={() => setMobileMenuOpen(false)}
                className="block py-2 text-sm font-medium text-slate-700 hover:text-emerald-600"
              >
                Create Donation
              </Link>
            </>
          ) : (
            <div className="pt-2 flex flex-col gap-2">
              <Link href="/sign-in" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="outline" className="w-full">
                  Sign In
                </Button>
              </Link>
              <Link href="/sign-up" onClick={() => setMobileMenuOpen(false)}>
                <Button className="w-full">Get Started</Button>
              </Link>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
