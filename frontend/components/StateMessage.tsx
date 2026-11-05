interface StateMessageProps {
  title: string;
  description?: string;
  tone?: "muted" | "error";
}

export function StateMessage({ title, description, tone = "muted" }: StateMessageProps) {
  return (
    <div className={`state-message ${tone === "error" ? "state-error" : ""}`} role="status">
      <p className="state-title">{title}</p>
      {description ? <p className="state-desc">{description}</p> : null}
    </div>
  );
}
