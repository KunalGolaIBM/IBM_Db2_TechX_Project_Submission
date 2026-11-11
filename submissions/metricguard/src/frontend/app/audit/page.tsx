import type { Metadata } from "next";
import { AuditList } from "@/components/audit/AuditList";

export const metadata: Metadata = { title: "Audit history · MetricGuard" };
export default function AuditPage() { return <AuditList />; }
