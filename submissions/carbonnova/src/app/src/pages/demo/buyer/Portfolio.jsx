import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, toneForStatus } from '../Shared';

export default function BuyerPortfolio() {
  const { user } = useAuthStore(); const actor={actor_role:'buyer',actor_id:user?.id};
  const balQ = useQuery({ queryKey:['bal',actor.actor_id], queryFn:()=>api.listBalances(actor) });
  const txQ = useQuery({ queryKey:['tx',actor.actor_id], queryFn:()=>api.listTransactions(actor) });
  return <Page title="My Portfolio" subtitle="Acquired demo credits and transaction status. Not registry-issued certificates.">
    <Card><div className="text-sm">Acquired credits: <b>{balQ.data?.balance?.acquired_credits ?? 0}</b></div></Card>
    <Card><Table cols={['Project','Quantity','Amount','Status','Date']} rows={(txQ.data?.transactions||[]).map(t=>[t.project_name,t.quantity,`${t.currency||'USD'} ${t.total_amount}`,<Badge tone={toneForStatus(t.status)}>{t.status}</Badge>,new Date(t.created_at).toLocaleString()])}/></Card>
  </Page>;
}
