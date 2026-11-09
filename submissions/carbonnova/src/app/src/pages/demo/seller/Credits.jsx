import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../lib/api';
import { useAuthStore } from '../../../stores/authStore';
import { Page, Card, Table, Badge, toneForStatus } from '../Shared';

export default function SellerCredits() {
  const { user } = useAuthStore(); const actor = { actor_role:'seller', actor_id:user?.id };
  const balQ = useQuery({ queryKey:['bal',actor.actor_id], queryFn:()=>api.listBalances(actor) });
  const listQ = useQuery({ queryKey:['mlist',actor.actor_id], queryFn:()=>api.listMarketplaceListings(actor) });
  const b = balQ.data?.balance||{};
  return <Page title="My Credits" subtitle="Track available, listed, and sold credit balances. Demonstration ledger; not registry-issued credits.">
    <div className="grid sm:grid-cols-4 gap-4"><Card><div className="text-xs font-bold uppercase text-[#5B7767]">Available</div><div className="text-3xl font-extrabold">{b.available_credits ?? 0}</div></Card><Card><div className="text-xs font-bold uppercase text-[#5B7767]">Sold</div><div className="text-3xl font-extrabold">{b.sold_credits ?? 0}</div></Card><Card><div className="text-xs font-bold uppercase text-[#5B7767]">Listed context</div><div className="text-3xl font-extrabold">{b.listed_credits ?? 0}</div></Card><Card><div className="text-xs font-bold uppercase text-[#5B7767]">Acquired</div><div className="text-3xl font-extrabold">{b.acquired_credits ?? 0}</div></Card></div>
    <Card><h2 className="font-bold mb-3">Listings affecting credit availability</h2><Table cols={['Project','Status','Available','Total','Sold']} rows={(listQ.data?.listings||[]).map(l=>[l.project_name,<Badge tone={toneForStatus(l.market_status)}>{l.market_status}</Badge>,l.quantity_available,l.quantity_total,l.quantity_sold||0])}/></Card>
  </Page>;
}
