import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <div className="auth-page">
      <div className="auth-intro">
        <h1>登录微信洞察</h1>
        <p className="muted">
          支持微信扫码或账号密码登录。登录后首次使用需填写一份信息登记，审核通过后即可使用全部数据功能。
        </p>
      </div>
      <LoginForm />
    </div>
  );
}
