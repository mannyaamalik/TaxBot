import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "TaxMitra — Indian Income Tax & GST Assistant",
  description:
    "Get instant, cited answers to your Income Tax and GST questions. Powered by RAG over official Indian tax documents.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "TaxMitra",
  },
  openGraph: {
    title: "TaxMitra — Indian Income Tax & GST Assistant",
    description: "AI-powered Q&A over Indian tax law — ITR, GST, TDS, Capital Gains.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#FF9933",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          storageKey="taxmitra-theme"
          value={{ dark: "dark", light: "theme-light" }}
        >
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              classNames: {
                toast:
                  "glass border border-[var(--color-border)] text-[var(--color-text-primary)] !font-[var(--font-ui)]",
                title: "font-semibold",
                description: "text-[var(--color-text-secondary)]",
              },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
