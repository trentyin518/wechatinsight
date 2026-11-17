import { StateMessage } from "@/components/StateMessage";

const TITLES: Record<string, string> = {
  "rank/industry": "行业排行榜",
  "rank/subject": "同主体排行",
  "ads/find": "广告找号",
  "ads/category": "广告分类",
  "ads/hotwords": "广告热词",
};

export default async function ConsolePlaceholderPage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params;
  const title = TITLES[slug.join("/")] ?? "该功能";

  return (
    <StateMessage title={`${title} · 建设中`} description="该功能正在接入数据，敬请期待。" />
  );
}
