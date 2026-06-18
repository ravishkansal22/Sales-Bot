import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { NegotiationProvider } from "../hooks/useNegotiationState";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ghost Negotiator | B2B Revenue Intelligence Simulation Engine",
  description: "Ghost Negotiator is a futuristic revenue intelligence platform that simulates multiple negotiation futures, calibrates customer digital twins, and selects optimal B2B contract strategies.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <NegotiationProvider>
          {children}
        </NegotiationProvider>
      </body>
    </html>
  );
}
