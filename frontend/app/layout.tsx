/**
 * Root layout (S3.7.1).
 *
 * RSC by default (no "use client" -- B1, U1). Reads the per-request CSP
 * nonce via `await headers()` (B3 / FD3.CSP3) so any inline script we
 * inject is whitelisted by the strict CSP set in `middleware.ts`.
 *
 * Per FE-AP-12 (AUTO-REJECT): the nonce is exposed via a `<meta>` tag,
 * NEVER via `dangerouslySetInnerHTML`. Client components read it through
 * `document.querySelector('meta[name="csp-nonce"]')?.getAttribute('content')`.
 *
 * Theme management uses `next-themes` per Style Guide §2 prescription.
 * The `ThemeProvider` is a client component wrapper imported from a leaf
 * file to keep the root layout as RSC.
 */

import "./globals.css";
import { headers } from "next/headers";
import { ThemeProvider } from "@/app/theme-provider";

export const metadata = {
  title: "Agent",
  description: "Claude-class chat with the ReAct agent",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): Promise<React.JSX.Element> {
  const h = await headers();
  const nonce = h.get("x-nonce") ?? "";
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="csp-nonce" content={nonce} />
      </head>
      <body>
        <ThemeProvider
          attribute="data-theme"
          defaultTheme="system"
          enableSystem
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
