import type { Metadata } from "next";
import { AuditDetailView } from "@/components/audit/AuditDetailView";

export const metadata: Metadata = { title: "Audit entry · MetricGuard" };
export default async function AuditDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AuditDetailView id={id} />;
}
