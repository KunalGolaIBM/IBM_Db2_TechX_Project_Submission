import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, Btn, toneForStatus } from '../Shared';

function Manager({ roleFilter, title }) {
  const { user } = useAuthStore(); const actor={actor_role:'admin',actor_id:user?.id}; const qc=useQueryClient();
  const q = useQuery({ queryKey:['users'], queryFn:()=>api.platformUsers(actor) });
  const mut = useMutation({ mutationFn:({id,status})=>api.setUserStatus(id,{ actor_role:'admin', actor_id:actor.actor_id, status, reason:`Admin set ${status} (demo)` }), onSuccess:()=>qc.invalidateQueries({queryKey:['users']}) });
  const users=(q.data?.users||[]).filter(u=>!roleFilter||u.role===roleFilter);
  return <Page title={title} subtitle="Inspect and manage demo users. Actions are recorded in audit logs.">
    <Card><Table cols={['Name','Role','Organization','Status','Actions']} rows={users.map(u=>[<div><div className="font-semibold">{u.full_name}</div><div className="text-xs text-[#6A8576]">{u.email}</div></div>,u.role,u.organization||'—',<Badge tone={toneForStatus(u.status)}>{u.status}</Badge>, <div className="flex flex-wrap gap-1">{['approved','suspended','banned','active'].map(s=><Btn key={s} variant={s==='approved'||s==='active'?'secondary':s==='suspended'?'secondary':'danger'} onClick={()=>mut.mutate({id:u.id,status:s})}>{s}</Btn>)}</div>])}/></Card>
  </Page>;
}
export function AdminUsers(){ return <Manager title="User Management" />; }
export function AdminSellers(){ return <Manager roleFilter="seller" title="Seller Management" />; }
export function AdminBuyers(){ return <Manager roleFilter="buyer" title="Buyer Management" />; }
export default AdminUsers;
