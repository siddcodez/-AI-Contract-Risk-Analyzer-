"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { register as registerApi } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorBanner } from "@/components/ui/error-banner";
import { Building2, ShieldCheck } from "lucide-react";

const signupSchema = z.object({
  full_name: z.string().min(1, "Full name is required"),
  org_name: z.string().min(1, "Organization name is required"),
  email: z.string().email("Please enter a valid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters long")
    .max(128, "Password too long"),
});

type SignupFormData = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const { loginUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
  });

  const onSubmit = async (data: SignupFormData) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await registerApi(data);
      await loginUser(response.access_token);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Registration failed. Please verify your details.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary-container text-white shadow-lg mb-4">
            <Building2 className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold text-on-surface tracking-tight">
            Create an Account
          </h1>
          <p className="text-sm text-on-surface-variant mt-1.5">
            Register your organization for AI contract risk analysis
          </p>
        </div>

        {/* Auth Card */}
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-6 md:p-8 shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
          {error && <ErrorBanner message={error} className="mb-6" />}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-on-surface-variant mb-1.5">
                Full Name
              </label>
              <Input
                placeholder="Alex Rivera"
                autoComplete="name"
                error={errors.full_name?.message}
                {...register("full_name")}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-on-surface-variant mb-1.5">
                Organization Name
              </label>
              <Input
                placeholder="Acme Legal Tech"
                autoComplete="organization"
                error={errors.org_name?.message}
                {...register("org_name")}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-on-surface-variant mb-1.5">
                Work Email
              </label>
              <Input
                type="email"
                placeholder="alex@acme.com"
                autoComplete="email"
                error={errors.email?.message}
                {...register("email")}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-on-surface-variant mb-1.5">
                Password
              </label>
              <Input
                type="password"
                placeholder="Minimum 8 characters"
                autoComplete="new-password"
                error={errors.password?.message}
                {...register("password")}
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full h-11 mt-2 text-sm font-bold"
              isLoading={isLoading}
            >
              Create Account
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t border-outline-variant/40 text-center">
            <p className="text-xs text-on-surface-variant">
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-primary font-semibold hover:underline"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Security badge footer */}
        <div className="flex items-center justify-center gap-2 mt-8 text-xs text-on-surface-variant/70">
          <ShieldCheck className="w-4 h-4 text-primary" />
          <span>Multi-tenant Row-Level Security Enforced</span>
        </div>
      </div>
    </div>
  );
}
