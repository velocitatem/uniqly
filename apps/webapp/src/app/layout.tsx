import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Analytics } from "@vercel/analytics/next"


const fontVariables = "font-sans";

export const metadata: Metadata = {
    title: "Uniqly",
    description: "Unique streams of inteligence tailored to your demands.",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className={`${fontVariables} antialiased`}>
                <main className="min-h-screen">
                    {children}
                </main>
                <Analytics/>
            </body>
        </html>
    );
}
