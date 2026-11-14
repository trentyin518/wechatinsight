import type { OnboardingStatus } from "./types";

/** Where a user should land based on their onboarding status. */
export function routeForStatus(status: OnboardingStatus): string {
  switch (status) {
    case "approved":
      return "/";
    case "pending":
      return "/onboarding/pending";
    case "rejected":
      return "/onboarding/rejected";
    default:
      return "/onboarding";
  }
}
