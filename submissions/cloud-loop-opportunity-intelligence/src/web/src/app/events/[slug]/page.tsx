"use client";

import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, use } from "react";
import {
  ExternalLink, Clock, MapPin, Calendar, CheckCircle2,
  Gift, Globe, Bookmark, Zap, ArrowLeft, Star, Users
} from "lucide-react";
import { events } from "@/features/events";
import { EventCard } from "@/features/events/components/EventCard";
import { StatusSelector } from "@/components/ui/StatusSelector";
import { useAuth } from "@clerk/nextjs";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn, formatDate } from "@/lib/utils";

export default function EventDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { getEventBySlug, events: liveEvents } = useOpportunities();
  const event = getEventBySlug(slug) || events.find((e) => e.slug === slug || e.id === slug);
  const { isSignedIn } = useAuth();
  const [isBookmarked, setIsBookmarked] = useState(false);

  useEffect(() => {
    if (event && typeof window !== "undefined") {
      setIsBookmarked(localStorage.getItem(`bookmarked_${event.id}`) === "true");
    }
  }, [event]);

  if (!event) notFound();

  const related = (liveEvents.length > 0 ? liveEvents : events)
    .filter((e) => e.id !== event.id && (e.organizer === event.organizer || e.type === event.type))
    .slice(0, 2);


  const handleBookmark = async () => {
    const next = !isBookmarked;
    localStorage.setItem(`bookmarked_${event.id}`, next ? "true" : "false");
    setIsBookmarked(next);

    if (isSignedIn) {
      try {
        await fetch("/api/opportunities/status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ opportunityId: event.id, bookmarked: next }),
        });
      } catch (err) {
        console.error("Failed to sync bookmark to Supabase:", err);
      }
    }
  };

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-20">
      <div className="bg-gradient-hero border-b border-border dark:border-dark-border py-14 px-4">
        <div className="container-narrow">
          <Link href="/events" className="inline-flex items-center gap-2 text-xs font-semibold text-text-secondary hover:text-primary mb-6 transition-colors">
            <ArrowLeft size={14} /> Back to Events
          </Link>
          <div className="flex items-start gap-5 mb-6">
            <div className="shrink-0 w-16 h-16 rounded-xl bg-secondary/10 dark:bg-primary/10 flex items-center justify-center font-bold text-lg text-secondary dark:text-primary">
              {event.organizer[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="text-[10px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded-full bg-secondary/10 text-secondary dark:bg-primary/10 dark:text-primary">
                  {event.type}
                </span>
                <span className="text-[10px] font-medium px-2 py-1 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                  {event.isOnline ? "Online" : "In-Person"}
                </span>
              </div>
              <h1 className="text-3xl md:text-4xl font-bold text-text-primary dark:text-dark-text-primary leading-tight">{event.title}</h1>
              <p className="text-text-secondary dark:text-dark-text-secondary mt-1">organized by {event.organizer}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-text-secondary dark:text-dark-text-secondary mb-8">
            <span className="flex items-center gap-1.5"><Calendar size={14} /> Date: {formatDate(event.date)}</span>
            <span className="flex items-center gap-1.5"><MapPin size={14} /> {event.location}</span>
            {event.registered && (
              <span className="flex items-center gap-1.5"><Users size={14} /> {event.registered.toLocaleString()} registered</span>
            )}
          </div>
          <div className="flex flex-wrap gap-3 items-center">
            <a href={event.applyUrl || "https://www.google.com"} target="_blank" rel="noopener noreferrer"
              className="btn-gradient px-6 py-3 rounded-pill text-sm font-semibold text-white inline-flex items-center gap-2 shadow-lg hover:scale-[1.02] transition-transform">
              Register Now <ExternalLink size={15} />
            </a>
            <button
              onClick={handleBookmark}
              className={cn(
                "p-3 rounded-full border border-border dark:border-dark-border text-text-primary dark:text-dark-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-all",
                isBookmarked ? "text-amber-500 bg-amber-50 dark:bg-amber-950/20 border-amber-300" : ""
              )}
              aria-label="Bookmark this event"
            >
              <Bookmark size={16} className={isBookmarked ? "fill-amber-500" : ""} />
            </button>
            <StatusSelector id={event.id} />
          </div>
        </div>
      </div>

      <div className="container-narrow py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-10">
            <div>
              <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
                Event Description
              </h2>
              <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed">{event.description}</p>
            </div>
            {event.prize && (
              <div>
                <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
                  🏆 Prizes & Rewards
                </h2>
                <div className="p-4 rounded-xl border border-accent/20 bg-accent/5 text-sm text-accent font-medium leading-relaxed">
                  {event.prize}
                </div>
              </div>
            )}
            <div>
              <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
                Tags
              </h2>
              <div className="flex flex-wrap gap-2">
                {event.tags.map((tag) => (
                  <span key={tag} className="text-xs px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 text-text-primary dark:text-dark-text-primary font-medium">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-5">
            <div className="card-base p-5 space-y-4">
              <h3 className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">Event Info</h3>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Type</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary">{event.type}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Location</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary">{event.isOnline ? "Online" : "In-Person"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Registration Deadline</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary">{event.registrationDeadline}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {related.length > 0 && (
          <div className="mt-14 pt-10 border-t border-border dark:border-dark-border">
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-6">Related Events</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {related.map((e) => <EventCard key={e.id} event={e} />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
