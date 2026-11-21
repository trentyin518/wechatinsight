export function ResultsPending({ mode }: { mode: "name" | "article" }) {
  return (
    <div className="console-hint" role="status" aria-live="polite">
      {mode === "article"
        ? "正在检索文章内容…（首次检索会调用数据源，可能需要几秒）"
        : "正在检索公众号…（首次检索会调用数据源，可能需要几秒）"}
    </div>
  );
}
