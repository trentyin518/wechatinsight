"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { submitOnboarding, uploadProof } from "@/lib/clientApi";
import { toApiError } from "@/lib/errors";

const CHANNELS = [
  { value: "search_engine", label: "百度等搜索引擎" },
  { value: "wechat_article", label: "公众号文章" },
  { value: "friend_referral", label: "朋友推荐" },
  { value: "media_site", label: "媒体平台或网站" },
  { value: "other", label: "其他" },
];

const USER_TYPES = [
  { value: "advertiser", label: "广告主" },
  { value: "brand", label: "品牌方" },
  { value: "agency", label: "广告媒介机构" },
  { value: "public_opinion", label: "舆情机构" },
  { value: "account_owner", label: "号主" },
  { value: "agency4a", label: "4A公司" },
  { value: "other", label: "其他" },
];

export function OnboardingForm({ rejectedReason }: { rejectedReason?: string | null }) {
  const router = useRouter();
  const [sourceChannel, setSourceChannel] = useState("search_engine");
  const [sourceOther, setSourceOther] = useState("");
  const [userType, setUserType] = useState("advertiser");
  const [userTypeOther, setUserTypeOther] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [needs, setNeeds] = useState("");

  const [proofId, setProofId] = useState<number | null>(null);
  const [proofName, setProofName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const res = await uploadProof(file);
      setProofId(res.proof_id);
      setProofName(res.original_name || "已上传");
    } catch (err) {
      setProofId(null);
      setProofName(null);
      setError(toApiError(err).message);
    } finally {
      setUploading(false);
    }
  }

  function validate(): string | null {
    if (!companyName.trim()) return "请填写公司名字。";
    if (!contactName.trim()) return "请填写您的名字。";
    if (!contactPhone.trim()) return "请填写您的联系电话。";
    if (!proofId) return "请上传证明材料。";
    if (sourceChannel === "other" && !sourceOther.trim()) return "选择「其他」时请填写具体途径。";
    if (userType === "other" && !userTypeOther.trim()) return "选择「其他」时请填写具体类型。";
    return null;
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const message = validate();
    if (message) {
      setError(message);
      return;
    }
    setSubmitting(true);
    try {
      await submitOnboarding({
        source_channel: sourceChannel,
        source_other: sourceOther.trim() || undefined,
        user_type: userType,
        user_type_other: userTypeOther.trim() || undefined,
        company_name: companyName.trim(),
        contact_name: contactName.trim(),
        contact_phone: contactPhone.trim(),
        needs: needs.trim() || undefined,
        proof_id: proofId as number,
      });
      router.push("/onboarding/pending");
      router.refresh();
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="onboarding-form card" onSubmit={onSubmit}>
      {rejectedReason ? (
        <p className="form-error">上次登记被驳回：{rejectedReason}。请修改后重新提交。</p>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}

      <fieldset className="form-fieldset">
        <legend>您是通过什么途径了解到我们的？<span className="req">*</span></legend>
        <div className="radio-group">
          {CHANNELS.map((c) => (
            <label key={c.value} className="radio-option">
              <input
                type="radio"
                name="source_channel"
                value={c.value}
                checked={sourceChannel === c.value}
                onChange={() => setSourceChannel(c.value)}
              />
              {c.label}
            </label>
          ))}
        </div>
        {sourceChannel === "other" ? (
          <input
            className="search-input"
            value={sourceOther}
            onChange={(e) => setSourceOther(e.target.value)}
            placeholder="请填写具体途径"
          />
        ) : null}
      </fieldset>

      <fieldset className="form-fieldset">
        <legend>您属于哪类人群？<span className="req">*</span></legend>
        <div className="radio-group">
          {USER_TYPES.map((t) => (
            <label key={t.value} className="radio-option">
              <input
                type="radio"
                name="user_type"
                value={t.value}
                checked={userType === t.value}
                onChange={() => setUserType(t.value)}
              />
              {t.label}
            </label>
          ))}
        </div>
        {userType === "other" ? (
          <input
            className="search-input"
            value={userTypeOther}
            onChange={(e) => setUserTypeOther(e.target.value)}
            placeholder="请填写具体类型"
          />
        ) : null}
      </fieldset>

      <label className="field">
        <span>公司名字<span className="req">*</span></span>
        <input
          className="search-input"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="请填写您的公司名字"
        />
      </label>

      <div className="field">
        <span>上传证明<span className="req">*</span></span>
        <p className="muted small">请上传公司证明（如营业执照、工牌、名片、账号截图等，支持 JPG/PNG/WEBP/PDF，≤5MB）。</p>
        <input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf" onChange={onFileChange} />
        {uploading ? <span className="muted small">上传中…</span> : null}
        {proofName ? <span className="upload-ok">已上传：{proofName}</span> : null}
      </div>

      <label className="field">
        <span>您的名字<span className="req">*</span></span>
        <input
          className="search-input"
          value={contactName}
          onChange={(e) => setContactName(e.target.value)}
          placeholder="请填写您的名字"
        />
      </label>

      <label className="field">
        <span>您的联系电话<span className="req">*</span></span>
        <input
          className="search-input"
          inputMode="numeric"
          value={contactPhone}
          onChange={(e) => setContactPhone(e.target.value)}
          placeholder="请填写您的联系电话"
        />
      </label>

      <label className="field">
        <span>您的需求是什么（可选）</span>
        <textarea
          className="search-input textarea"
          value={needs}
          onChange={(e) => setNeeds(e.target.value)}
          placeholder="可简要描述您的需求"
          rows={3}
        />
      </label>

      <button className="btn btn-primary" type="submit" disabled={submitting || uploading}>
        {submitting ? "提交中…" : "提交登记"}
      </button>
    </form>
  );
}
