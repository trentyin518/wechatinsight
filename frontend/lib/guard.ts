import { redirect } from "next/navigation";

import { getServerCurrentUser } from "./api";

export function authEnforced(): boolean {
  return process.env.NEXT_PUBLIC_AUTH_ENFORCED === "true";
}

/**
 * Server-side page gate. Only active when NEXT_PUBLIC_AUTH_ENFORCED is true so
 * the public (gray) rollout keeps working. Individual pages call this before
 * rendering protected content.
 */
export async function requireApprovedOrRedirect(): Promise<void> {
  if (!authEnforced()) return;
  const user = await getServerCurrentUser();
  if (!user) redirect("/login");
  switch (user.onboarding_status) {
    case "approved":
      return;
    case "pending":
      redirect("/onboarding/pending");
    case "rejected":
      redirect("/onboarding/rejected");
    default:
      redirect("/onboarding");
  }
}

export async function requireAdminOrRedirect(): Promise<void> {
  if (!authEnforced()) return;
  const user = await getServerCurrentUser();
  if (!user) redirect("/login");
  if (!user.is_admin) redirect("/");
}
