import Link from "next/link";
import { redirect } from "next/navigation";

import { StateMessage } from "@/components/StateMessage";
import { getServerCurrentUser, getServerOnboardingStatus } from "@/lib/api";

export default async function OnboardingPendingPage() {
  const user = await getServerCurrentUser();
  if (!user) {
    return <StateMessage tone="error" title="请先登录" description="登录后才能查看审核状态。" />;
  }

  const status = await getServerOnboardingStatus();
  if (status?.status === "approved") redirect("/");
  if (status?.status !== "pending") redirect("/onboarding");

  return (
    <div className="auth-page">
      <div className="auth-card">
        <StateMessage
          title="资料审核中"
          description="我们已收到您的信息登记，审核通过后即可使用。审核结果会在本页更新。"
        />
        <p className="muted small" style={{ marginTop: 16 }}>
          <Link href="/onboarding/pending">刷新状态</Link>
        </p>
      </div>
    </div>
  );
}
