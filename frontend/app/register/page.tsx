import { RegisterForm } from "@/components/RegisterForm";

export default function RegisterPage() {
  return (
    <div className="auth-page">
      <div className="auth-intro">
        <h1>注册账号</h1>
        <p className="muted">使用手机号注册，注册后需填写信息登记，审核通过后即可使用。</p>
      </div>
      <RegisterForm />
    </div>
  );
}
