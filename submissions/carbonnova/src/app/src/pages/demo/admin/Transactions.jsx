import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, toneForStatus } from '../Shared';
export default function AdminTransactions(){ const {user}=useAuthStore(); const q=useQuery({queryKey:['tx','admin'],queryFn:()=>api.listTransactions({actor_role:'admin',actor_id:user?.id})}); return <Page title="Transactions" subtitle="Monitor all credit transactions, quantities, amounts, and status."><Card><Table cols={['Project','Buyer','Seller','Qty','Amount','Status','Date']} rows={(q.data?.transactions||[]).map(t=>[t.project_name,t.buyer_id,t.seller_id,t.quantity,`${t.currency||'USD'} ${t.total_amount}`,<Badge tone={toneForStatus(t.status)}>{t.status}</Badge>,new Date(t.created_at).toLocaleString()])}/></Card></Page>; }
