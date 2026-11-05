"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="state-message state-error" role="alert">
      <p className="state-title">页面加载出错</p>
      <p className="state-desc">
        暂时无法加载该页面。数据源故障不会导致整个站点不可用，你可以稍后重试或返回首页。
      </p>
      <div style={{ marginTop: 16, display: "flex", gap: 10, justifyContent: "center" }}>
        <button className="btn btn-primary" onClick={() => reset()}>
          重试
        </button>
        <a className="btn" href="/">
          返回首页
        </a>
      </div>
    </div>
  );
}
