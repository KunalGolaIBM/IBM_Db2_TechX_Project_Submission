import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table } from '../Shared';
export default function Audit(){ const {user}=useAuthStore(); const q=useQuery({queryKey:['audit'],queryFn:()=>api.platformAudit({actor_role:'admin',actor_id:user?.id})}); return <Page title="Audit Logs" subtitle="Who performed an action, what changed, and when."><Card><Table cols={['Time','Actor','Action','Entity','Reason']} rows={(q.data?.audit_logs||[]).map(a=>[new Date(a.at).toLocaleString(), `${a.actor_role||''} ${a.actor_id||''}`, a.action, `${a.entity_type||''} ${a.entity_id||''}`, a.reason||'—'])}/></Card></Page>; }
