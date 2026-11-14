import Link from "next/link";
import { redirect } from "next/navigation";

import { StateMessage } from "@/components/StateMessage";
import { getServerCurrentUser, getServerOnboardingStatus } from "@/lib/api";

export default async function OnboardingRejectedPage() {
  const user = await getServerCurrentUser();
  if (!user) {
    return <StateMessage tone="error" title="请先登录" description="登录后才能查看审核状态。" />;
  }

  const status = await getServerOnboardingStatus();
  if (status?.status === "approved") redirect("/");
  if (status?.status !== "rejected") redirect("/onboarding");

  return (
    <div className="auth-page">
      <div className="auth-card">
        <StateMessage
          tone="error"
          title="资料未通过审核"
          description={status.submission?.reject_reason || "请修改信息后重新提交。"}
        />
        <p style={{ marginTop: 16 }}>
          <Link className="btn btn-primary" href="/onboarding">
            修改并重新提交
          </Link>
        </p>
      </div>
    </div>
  );
}
