import Link from "next/link";

import { SearchForm } from "@/components/SearchForm";

const CATEGORIES = ["科技", "财经", "生活方式", "教育", "健康"];

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <h1>搜索公众号，查看真实可获取的数据</h1>
        <p>
          查询公众号资料与历史文章，浏览数据源实际提供的阅读量、点赞量与在看数。平台只展示已收录账号，
          并明确标注数据来源与采集时间——缺失的指标不会显示为 0。
        </p>
        <SearchForm />
      </section>

      <section className="section">
        <h2 className="section-title">按分类浏览</h2>
        <div className="chip-row">
          {CATEGORIES.map((category) => (
            <Link className="chip" key={category} href={`/search?q=${encodeURIComponent(category)}`}>
              {category}
            </Link>
          ))}
        </div>
      </section>

      <div className="notice">
        <strong>数据说明：</strong>
        本平台为第一版最小闭环，搜索结果来自本地已收录账号；本地未命中时会进行一次受控的第三方查询。
        排行榜与趋势分析将在数据积累稳定后提供。所有指标均以第三方数据源实际返回为准。
      </div>
    </>
  );
}
