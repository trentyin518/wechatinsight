import { AdminReviews } from "@/components/AdminReviews";
import { requireAdminOrRedirect } from "@/lib/guard";

export default async function AdminReviewsPage() {
  await requireAdminOrRedirect();

  return (
    <div className="auth-page">
      <div className="auth-intro">
        <h1>信息登记审核</h1>
        <p className="muted">审核用户提交的信息登记，通过后用户即可使用数据功能。</p>
      </div>
      <AdminReviews />
    </div>
  );
}
