import { redirect } from "next/navigation";

import { OnboardingForm } from "@/components/OnboardingForm";
import { StateMessage } from "@/components/StateMessage";
import { getServerCurrentUser, getServerOnboardingStatus } from "@/lib/api";

export default async function OnboardingPage() {
  const user = await getServerCurrentUser();
  if (!user) {
    return (
      <StateMessage
        tone="error"
        title="请先登录"
        description="登录后才能填写信息登记。请前往登录页登录。"
      />
    );
  }

  const status = await getServerOnboardingStatus();
  if (status?.status === "approved") redirect("/");
  if (status?.status === "pending") redirect("/onboarding/pending");
  if (status?.status === "rejected") redirect("/onboarding/rejected");

  return (
    <div className="auth-page">
      <div className="auth-intro">
        <h1>完善信息登记</h1>
        <p className="muted">
          首次使用前请认真填写以下内容，本问卷仅需填写一次；带 <span className="req">*</span> 为必选项，其余可选。
        </p>
      </div>
      <OnboardingForm />
    </div>
  );
}
