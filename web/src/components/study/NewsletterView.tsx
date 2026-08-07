"use client";

import { useState } from "react";
import type { Article, Newsletter } from "@/lib/types";

// POPROX palette (matches the reference newsletter template).
const TEAL = "#008f83";
const NAVY = "#003c5e";
const BORDER = "#bdbdc5";
const CARD_BG = "#f8f8ff";
const POPROX_LOGO =
  "https://poprox.ai/assets/images/logos_and_icons/logo_white.png";

function Thumb({ article }: { article: Article }) {
  const [failed, setFailed] = useState(false);
  if (!article.image || failed) {
    return (
      <div
        className="flex h-[120px] w-[180px] shrink-0 items-center justify-center rounded-sm px-2 text-center"
        style={{ background: "#e6e8f0", color: NAVY }}
      >
        <span className="text-[11px] font-semibold uppercase tracking-wide">
          {article.label || "POPROX"}
        </span>
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={article.image}
      alt={article.headline}
      width={180}
      height={120}
      onError={() => setFailed(true)}
      className="h-[120px] w-[180px] shrink-0 object-cover"
      style={{ objectPosition: "center top" }}
    />
  );
}

function ArticleRow({ article }: { article: Article }) {
  return (
    <div className="flex gap-3 px-4 py-4 sm:px-[18px]">
      <Thumb article={article} />
      <div className="min-w-0">
        {article.label && (
          <div
            className="mb-1 text-[13px] font-bold leading-tight"
            style={{ color: NAVY, fontFamily: "Tahoma, Geneva, sans-serif" }}
          >
            {article.label}
          </div>
        )}
        <div
          className="mb-2 text-[17px] font-bold leading-snug"
          style={{ color: TEAL, fontFamily: "Georgia, 'Times New Roman', serif" }}
        >
          {article.headline}
        </div>
        <div
          className="text-[14px] leading-snug"
          style={{ color: "#111", fontFamily: "Tahoma, Geneva, sans-serif" }}
        >
          {article.summary}
        </div>
      </div>
    </div>
  );
}

export function NewsletterView({ newsletter }: { newsletter: Newsletter }) {
  return (
    <div
      className="mx-auto w-full max-w-[740px] overflow-hidden"
      style={{ background: CARD_BG, border: `1px solid ${BORDER}` }}
    >
      {/* Masthead */}
      <div className="px-3 py-4 text-center" style={{ background: TEAL }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={POPROX_LOGO}
          alt="POPROX News"
          width={280}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
          className="mx-auto block h-auto w-[280px] max-w-[90%]"
        />
      </div>
      {newsletter.edition_label && (
        <div
          className="px-4 py-1.5 text-center text-[12px]"
          style={{ color: NAVY, background: "#eef0f7" }}
        >
          {newsletter.edition_label}
        </div>
      )}

      {newsletter.sections.map((section, si) => (
        <div key={section.name}>
          {/* Section bar */}
          <div
            className="px-4 py-2 text-[19px] font-bold sm:px-[18px]"
            style={{
              background: NAVY,
              color: "#fff",
              fontFamily: "Tahoma, Geneva, sans-serif",
            }}
          >
            {section.name}
          </div>
          {section.articles.map((article, ai) => (
            <div key={`${si}-${ai}`}>
              <ArticleRow article={article} />
              {ai < section.articles.length - 1 && (
                <div className="px-4 sm:px-[18px]">
                  <div style={{ height: 1, background: BORDER }} />
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
