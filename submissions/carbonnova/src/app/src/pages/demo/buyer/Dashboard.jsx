import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card } from '../Shared';

export default function BuyerDashboard() {
  const { user } = useAuthStore(); const actor={actor_role:'buyer',actor_id:user?.id};
  const txQ = useQuery({ queryKey:['tx',actor.actor_id], queryFn:()=>api.listTransactions(actor) });
  const balQ = useQuery({ queryKey:['bal',actor.actor_id], queryFn:()=>api.listBalances(actor) });
  const mQ = useQuery({ queryKey:['market',actor], queryFn:()=>api.listMarketplaceListings(actor) });
  return <Page title="Buyer dashboard" subtitle="Discover, assess, and purchase eligible carbon credits (demonstration transactions).">
    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {[['Available listings',(mQ.data?.listings||[]).length],['Acquired credits',balQ.data?.balance?.acquired_credits ?? 0],['Transactions',(txQ.data?.transactions||[]).length],['Demo status','Active']].map(([k,v])=><Card key={k}><div className="text-xs uppercase font-bold text-[#5B7767]">{k}</div><div className="text-3xl font-extrabold mt-1">{v}</div></Card>)}
    </div>
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{[['/demo/buyer/marketplace','Global Marketplace'],['/demo/buyer/quality','Quality Assessment'],['/demo/buyer/documents','Document Verification'],['/demo/buyer/portfolio','My Portfolio'],['/demo/buyer/transactions','Transactions'],['/demo/buyer/explore','Explore Projects']].map(([to,l])=><Link key={to} to={to} className="bg-white border border-[#DCE6DE] rounded-2xl p-4 font-semibold hover:border-emerald-300">{l}</Link>)}</div>
  </Page>;
}
