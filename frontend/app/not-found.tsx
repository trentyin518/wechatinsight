import Link from "next/link";

export default function NotFound() {
  return (
    <div className="state-message">
      <p className="state-title">页面不存在</p>
      <p className="state-desc">你访问的页面或资源不在平台收录范围内。</p>
      <p style={{ marginTop: 16 }}>
        <Link className="btn" href="/">
          返回首页
        </Link>
      </p>
    </div>
  );
}
