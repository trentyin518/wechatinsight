import { AdminSyncHealth } from "@/components/AdminSyncHealth";
import { requireAdminOrRedirect } from "@/lib/guard";

export default async function AdminSyncPage() {
  await requireAdminOrRedirect();

  return (
    <div className="auth-page">
      <div className="auth-intro">
        <h1>同步任务健康度</h1>
        <p className="muted">
          查看同步队列的积压、24 小时吞吐与失败原因，快速判断是“没消费”还是“数据源异常”。
        </p>
      </div>
      <AdminSyncHealth />
    </div>
  );
}
