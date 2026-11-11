import type { Metadata } from "next";
import { CommunityPageContent } from "@/features/community";

export const metadata: Metadata = {
  title: "Community",
  description: "Join the Cloud Loop community — WhatsApp, Telegram, and LinkedIn.",
};

export default function CommunityPage() {
  return <CommunityPageContent />;
}
