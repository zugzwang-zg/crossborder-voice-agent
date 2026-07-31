import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Crossborder Voice｜跨境电商评论洞察台",
  description: "基于 1000 条英语与西语评论的可追溯消费者洞察看板。",
  openGraph: {
    title: "Crossborder Voice｜跨境电商评论洞察台",
    description: "1000 条英西双语评论，从统计信号直达消费者原文。",
    images: [{ url: "/social-preview.png", width: 1731, height: 909 }],
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
