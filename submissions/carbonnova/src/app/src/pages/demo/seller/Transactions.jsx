import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, toneForStatus } from '../Shared';

export default function SellerTransactions() {
  const { user } = useAuthStore(); const actor = { actor_role:'seller', actor_id:user?.id };
  const q = useQuery({ queryKey:['tx',actor.actor_id], queryFn:()=>api.listTransactions(actor) });
  return <Page title="Transactions" subtitle="Completed and pending credit transactions affecting your balance. Demo payments only.">
    <Card><Table cols={['Project','Buyer','Qty','Amount','Status','Date']} rows={(q.data?.transactions||[]).map(t=>[t.project_name,t.buyer_id,t.quantity,`${t.currency||'USD'} ${t.total_amount}`,<Badge tone={toneForStatus(t.status)}>{t.status}</Badge>, new Date(t.created_at).toLocaleString()])}/></Card>
  </Page>;
}
