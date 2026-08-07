import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EARN — Newsletter Feedback Study",
  description:
    "A research study on how people give feedback about personalized news newsletters.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
