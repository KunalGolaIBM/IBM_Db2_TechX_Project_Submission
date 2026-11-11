"use client";

import Link from "next/link";
import { Calendar, MapPin, Globe, Users } from "lucide-react";
import { StatusSelector } from "@/components/ui/StatusSelector";
import { formatDate } from "@/lib/utils";
import { Event } from "../types/Event";

export function EventCard({ event }: { event: Event }) {
  return (
    <Link href={`/events/${event.slug}`} className="block h-full">
      <div className="card-base p-5 h-full flex flex-col gap-4">
        {/* Type badge */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded-full bg-secondary/10 text-secondary dark:bg-primary/10 dark:text-primary">
            {event.type}
          </span>
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${event.isOnline ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"}`}>
            {event.isOnline ? <><Globe size={9} /> Online</> : <><MapPin size={9} /> In-person</>}
          </span>
        </div>

        {/* Title & Organizer */}
        <div>
          <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary leading-snug mb-1">
            {event.title}
          </p>
          <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{event.organizer}</p>
        </div>

        {/* Description */}
        <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed line-clamp-2 flex-1">
          {event.description}
        </p>

        {/* Prize */}
        {event.prize && (
          <div className="px-3 py-2 rounded-xl bg-accent/8 border border-accent/20">
            <p className="text-xs font-medium text-accent">🏆 {event.prize}</p>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-border dark:border-dark-border">
          <div className="flex flex-col gap-0.5 text-xs text-text-secondary dark:text-dark-text-secondary">
            <span className="flex items-center gap-1">
              <Calendar size={11} />
              {formatDate(event.date)}
            </span>
            {event.registered && (
              <span className="flex items-center gap-1 text-[10px] text-text-secondary/80">
                <Users size={10} /> {(event.registered / 1000).toFixed(0)}k registered
              </span>
            )}
          </div>
          <StatusSelector id={event.id} />
        </div>
      </div>
    </Link>
  );
}
