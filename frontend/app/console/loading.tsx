export default function ConsoleLoading() {
  return (
    <div className="console-hint" role="status" aria-live="polite">
      正在加载检索结果…（首次检索会调用数据源，可能需要几秒）
    </div>
  );
}
