import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sledge Change Order Intelligence",
  description: "Evidence-grounded construction document extraction",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
