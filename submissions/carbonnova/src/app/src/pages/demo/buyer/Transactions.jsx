import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, toneForStatus } from '../Shared';

export default function BuyerTransactions() {
  const { user } = useAuthStore(); const actor={actor_role:'buyer',actor_id:user?.id};
  const q = useQuery({ queryKey:['tx',actor.actor_id], queryFn:()=>api.listTransactions(actor) });
  return <Page title="Transactions" subtitle="Demonstration purchase history and status."><Card><Table cols={['Project','Qty','Price/credit','Total','Status','Date']} rows={(q.data?.transactions||[]).map(t=>[t.project_name,t.quantity,`$${t.price_per_credit}`,`${t.currency||'USD'} ${t.total_amount}`,<Badge tone={toneForStatus(t.status)}>{t.status}</Badge>,new Date(t.created_at).toLocaleString()])}/></Card></Page>;
}
