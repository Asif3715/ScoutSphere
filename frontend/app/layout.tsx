import type { Metadata, Viewport } from "next";
import {
  Azeret_Mono,
  Big_Shoulders,
  Schibsted_Grotesk,
} from "next/font/google";

import { Providers } from "@/components/providers";
import "./globals.css";

// Display: condensed stadium-signage letterforms. Body: a newsroom grotesk.
// Data: a mono with real character for ratings, squad numbers and stats.
const display = Big_Shoulders({
  variable: "--font-display-face",
  subsets: ["latin"],
  axes: ["opsz"],
});
const body = Schibsted_Grotesk({ variable: "--font-body", subsets: ["latin"] });
const data = Azeret_Mono({ variable: "--font-data", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ScoutSphere",
  description: "AI-powered football scouting and talent intelligence",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ece7da" },
    { media: "(prefers-color-scheme: dark)", color: "#0a110e" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${body.variable} ${data.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
