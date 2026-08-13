import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrossBorder Voice｜免费评论表格分析",
  description: "上传英语或西班牙语评论表格，在浏览器内免费查看高频问题、顾客反馈和下一步建议。",
  openGraph: {
    title: "CrossBorder Voice｜上传评论表格，快速看懂顾客反馈",
    description: "无需注册，不用 API Key。上传 CSV 或 XLSX，在浏览器内完成快速评论分析。",
    images: [{ url: "/og.png", width: 1731, height: 909 }],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
