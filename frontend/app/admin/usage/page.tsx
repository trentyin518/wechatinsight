import { AdminUsage } from "@/components/AdminUsage";
import { requireAdminOrRedirect } from "@/lib/guard";

export default async function AdminUsagePage() {
  await requireAdminOrRedirect();

  return (
    <div className="auth-page">
      <div className="auth-intro">
        <h1>用量与预算</h1>
        <p className="muted">查看数据源余额、今日/本月消耗与后台任务开关，及时发现异常扣费。</p>
      </div>
      <AdminUsage />
    </div>
  );
}
