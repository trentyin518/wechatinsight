import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { MetricGrid } from "@/components/MetricGrid";
import { StateMessage } from "@/components/StateMessage";
import { ApiError, getArticle, getArticleMetrics } from "@/lib/api";
import { formatDateTime, formatMetric, formatObservedChange, providerLabel } from "@/lib/format";

interface ArticlePageProps {
  params: Promise<{ id: string }>;
}

export default async function ArticlePage({ params }: ArticlePageProps) {
  const { id } = await params;

  try {
    const [article, history] = await Promise.all([getArticle(id), getArticleMetrics(id)]);

    return (
      <>
        <div className="breadcrumb">
          <Link href="/">首页</Link> /{" "}
          <Link href={`/accounts/${article.account_id}`}>公众号</Link> / 文章
        </div>

        <article>
          <h1 style={{ fontSize: "1.7rem", margin: "0 0 8px" }}>{article.title}</h1>
          <div className="meta-row">
            <a href={article.article_url} target="_blank" rel="noreferrer" className="badge">
              查看原文 ↗
            </a>
            <span>发布：{formatDateTime(article.published_at)}</span>
            {article.author ? <span>作者：{article.author}</span> : null}
            {article.is_original !== null ? (
              <span>{article.is_original ? "原创" : "非原创"}</span>
            ) : null}
          </div>

          {article.summary ? <p className="muted" style={{ marginTop: 16 }}>{article.summary}</p> : null}

          <section className="section">
            <h2 className="section-title">互动指标</h2>
            {article.metrics ? (
              <>
                <MetricGrid metrics={article.metrics} />
                <DataProvenance
                  provider={article.metrics.provider}
                  observedAt={article.metrics.observed_at}
                  label="指标采集"
                />
              </>
            ) : (
              <StateMessage
                title="暂无指标数据"
                description="数据源尚未提供该文章的互动指标，或尚未完成采集。"
              />
            )}
          </section>

          <section className="section">
            <h2 className="section-title">指标观测历史</h2>
            {history.points.length === 0 ? (
              <StateMessage title="暂无观测记录" description="该文章尚未产生任何指标快照。" />
            ) : (
              <>
                <p className="muted small">
                  观测阅读量变化：{formatObservedChange(
                    history.observed_read_change.delta,
                    history.observed_read_change.rate,
                  )}
                  {history.points.length < 2 ? "（仅有一次观测，不生成趋势曲线）" : ""}
                </p>
                <div className="history">
                  {history.points.map((point, index) => (
                    <div className="history-row" key={`${point.observed_at}-${index}`}>
                      <span>{formatDateTime(point.observed_at)}</span>
                      <span className="muted">
                        阅读 {formatMetric(point.read_count)} · 点赞 {formatMetric(point.like_count)} · 在看{" "}
                        {formatMetric(point.wow_count)} · {providerLabel(point.provider)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        </article>
      </>
    );
  } catch (error) {
    const apiError = error as ApiError;
    if (apiError.code === "NOT_FOUND") {
      return <StateMessage tone="error" title="文章不存在" description="该文章不在平台收录范围内。" />;
    }
    return (
      <StateMessage
        tone="error"
        title="加载失败"
        description={
          apiError.code === "DATA_SOURCE_UNAVAILABLE"
            ? "数据源暂时不可用，请稍后重试。"
            : apiError.message
        }
      />
    );
  }
}
