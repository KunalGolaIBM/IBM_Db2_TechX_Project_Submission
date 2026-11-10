import { Fragment, useEffect, useRef, useState } from "react";
import { api, fmt, type Finding } from "../api";
import { scrollToY } from "../lib/scroll";
import type { CloudInfo, CloudQuery, CloudScene, Lens } from "../components/CloudScene";

const QUERY_LABEL: Record<string, string> = { pyyaml: "PyYAML message", flashpix: "Pillow FlashPix" };
const STEPS = [
  { obj: "CALL NEEDLE.TRIAGE_MODE", says: "Keyword rank (BM25 in plain SQL) and meaning rank (DiskANN vector index, FETCH APPROX), fused by reciprocal rank fusion in one Db2 statement." },
  { obj: "CREATE PERMISSION", says: "Row access control decides which advisories each Db2 identity can read. Embargoed ones never leave Db2 for a junior analyst." },
  { obj: "FOR BUSINESS_TIME AS OF", says: "An exact package and version join over each service's deploy history says who is affected, and since when." },
];

export default function Landing() {
  return (
    <>
      <Hero />
      <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8">
        <section className="grid gap-8 border-b border-hair py-16 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16 lg:py-24">
          <h2 className="max-w-[16ch] font-display text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">Three Db2 features do the work</h2>
          <dl className="border-t border-hair">
            {STEPS.map((s) => (
              <div key={s.obj} className="grid gap-1 border-b border-hair py-5 sm:grid-cols-[250px_minmax(0,1fr)] sm:gap-8">
                <dt className="font-mono text-[13px] font-semibold text-accent-strong">{s.obj}</dt>
                <dd className="text-md text-ink-2">{s.says}</dd>
              </div>
            ))}
          </dl>
        </section>
        <FindingTeaser />
        <section className="flex flex-wrap items-center justify-between gap-6 py-16">
          <p className="max-w-[40ch] font-display text-2xl font-semibold tracking-[-0.02em]">Paste the rumour from the chat thread. Get the services, and since when.</p>
          <div className="flex flex-wrap items-center gap-5">
            <a href="#/triage" className="btn btn-primary no-underline">Open the triage console</a>
            <a href="#/how" className="text-sm">How it works</a>
          </div>
        </section>
      </div>
      <footer className="border-t border-hair">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-x-8 gap-y-2 px-4 py-6 text-xs text-mute sm:px-6 lg:px-8">
          <span><span className="font-mono font-semibold tracking-[0.08em] text-ink">NEEDLE</span> · team Needlepoint · IBM Db2Hack 2026</span>
          <span>Advisories: the OSV PyPI export. The service fleet is synthetic. Runs on 127.0.0.1 against your own Db2.</span>
        </div>
      </footer>
    </>
  );
}

function Hero() {
  const host = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<CloudScene | null>(null);
  const [info, setInfo] = useState<CloudInfo | null>(null);
  const [q, setQ] = useState("pyyaml");
  const [who, setWho] = useState<"all" | "p10">("all");
  const [plan, setPlan] = useState<"shared" | "router">("shared");
  const [ready, setReady] = useState(false);
  // why the 3D view is missing: the browser has no WebGL, or the corpus map (cloud.json / cloud.bin) did not load
  const [heroErr, setHeroErr] = useState<{ kind: "webgl" | "data"; message: string } | null>(null);
  const [paused, setPaused] = useState(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  const lens: Lens = who === "all" ? "all" : plan === "shared" ? "p10-shared" : "p10-router";
  const query: CloudQuery | undefined = info?.queries.find((x) => x.key === q);

  useEffect(() => {
    let disposed = false;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    import("../components/CloudScene").then(async ({ CloudScene: Scene, loadCloud }) => {
      const data = await loadCloud();
      if (disposed || !host.current) return;
      try {
        const s = new Scene(host.current, data, still);
        s.onFrame = (p) => {
          const el = label.current;
          if (!el) return;
          el.style.opacity = p ? "1" : "0";
          if (!p) return;
          const flip = host.current ? p.x > host.current.clientWidth - 150 : false;
          el.style.transform = `translate(${Math.round(flip ? p.x - 118 : p.x)}px, ${Math.round(p.y)}px)`;
        };
        sceneRef.current = s;
        setInfo(data.info);
        requestAnimationFrame(() => setReady(true));
      } catch (e) {
        setInfo(data.info);
        setHeroErr({ kind: "webgl", message: errText(e) });
      }
    }).catch((e) => { if (!disposed) setHeroErr({ kind: "data", message: errText(e) }); });
    const io = new IntersectionObserver(([e]) => sceneRef.current?.setRunning(e.isIntersecting));
    if (host.current) io.observe(host.current);
    return () => { disposed = true; io.disconnect(); sceneRef.current?.dispose(); sceneRef.current = null; };
  }, []);

  // Scroll story (desktop): the stage pins and four chapters step the scene through the finding.
  const storyRef = useRef<HTMLElement>(null);
  const railRef = useRef<HTMLOListElement>(null);
  const [chapter, setChapter] = useState(0);
  // the chapter that is leaving, kept on screen for its exit fade
  const [leaving, setLeaving] = useState(0);
  const prevChapter = useRef(0);
  useEffect(() => {
    if (prevChapter.current && prevChapter.current !== chapter) {
      setLeaving(prevChapter.current);
      const t = window.setTimeout(() => setLeaving(0), 240);
      prevChapter.current = chapter;
      return () => window.clearTimeout(t);
    }
    prevChapter.current = chapter;
  }, [chapter]);
  const jumpTo = (c: number) => {
    const el = storyRef.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + scrollY, span = el.offsetHeight - innerHeight;
    scrollToY(top + span * (0.08 + ((c - 1 + 0.15) / 4) * 0.92));
  };
  useEffect(() => {
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = storyRef.current;
        if (!el || innerWidth < 1024) { setChapter(0); return; }
        const r = el.getBoundingClientRect();
        const p = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - innerHeight)));
        const x = ((p - 0.08) / 0.92) * 4;
        setChapter(p < 0.08 ? 0 : Math.min(4, 1 + Math.floor(x)));
        railRef.current?.style.setProperty("--sub", p < 0.08 ? "0" : String(Math.min(1, x - Math.floor(Math.min(3.999, x)))));
      });
    };
    addEventListener("scroll", on, { passive: true });
    addEventListener("resize", on);
    on();
    return () => { removeEventListener("scroll", on); removeEventListener("resize", on); cancelAnimationFrame(raf); };
  }, []);
  const storyQuery = info?.queries.find((x) => x.key === "pyyaml");
  const effQuery = chapter === 0 ? query : storyQuery;
  const effLens: Lens = chapter === 0 ? lens : chapter === 3 ? "p10-shared" : chapter === 4 ? "p10-router" : "all";

  useEffect(() => { if (effQuery) sceneRef.current?.setState(effQuery, effLens); }, [effQuery, effLens, ready]);
  useEffect(() => { sceneRef.current?.setStory([0, 0, 0.55, 0.7, 0.5][chapter], chapter !== 1); }, [chapter, ready]);
  useEffect(() => { sceneRef.current?.setAuto(!paused); }, [paused, ready]);

  const batchVisible = query?.batch_visible_p10 ?? 0;
  const readout = !info || !query ? null
    : lens === "all" ? { n: "10 of 10", tone: "text-[#5fdbe3]", line: `All ${fmt.int(info.n)} public advisories visible. The 10 nearest to the question are lit.` }
      : lens === "p10-shared" ? { n: `${batchVisible} of 10`, tone: "text-affected-ink", line: `The vector index fetches a first batch of ${info.batch}, sized as if this analyst saw half the rows. The permission removes ${info.batch - batchVisible} (red). ${batchVisible} ${batchVisible === 1 ? "comes" : "come"} back.` }
        : { n: "10 of 10", tone: "text-[#5fdbe3]", line: `NEEDLE counts the ${fmt.int(info.p10_visible)} rows this analyst may read and runs an exact scan over them instead.` };

  const sv = storyQuery?.batch_visible_p10 ?? 0;
  const chapters = !info ? [] : [
    { name: "The corpus", title: `${fmt.int(info.n)} advisories, placed by meaning`,
      body: "Each point is a real Python security advisory. Points that sit close together mean similar things, so even a vague question usually lands near the advisories it is about." },
    { name: "The search", title: "A question arrives",
      body: "The question becomes a vector. Db2's vector index walks its graph toward it, one neighbour at a time, and collects the nearest advisories. Keyword search runs in the same SQL statement." },
    { name: "The permission", title: `Ask for 10. Get ${sv}.`,
      body: `An analyst who may read ${fmt.int(info.p10_visible)} advisories asks for 10. The shared plan fetches a first batch of ${info.batch}, sized as if everyone saw half the rows; row access control removes ${info.batch - sv} of them (red), and ${sv} ${sv === 1 ? "comes" : "come"} back.` },
    { name: "The router", title: "Count first, then search",
      body: `NEEDLE counts the ${fmt.int(info.p10_visible)} rows this analyst may read, then runs an exact scan over them. 10 of 10 come back, and none from outside the permission.` },
  ];

  return (
    <section ref={storyRef} aria-label="NEEDLE" className={`relative bg-[#0a0c0d] text-paper ${paused ? "hero-paused" : ""}`} data-testid="hero">
      <div className="relative overflow-hidden lg:sticky lg:top-14">
      <div aria-hidden className="absolute inset-0" style={{ background: "radial-gradient(ellipse 58% 62% at 66% 46%, #172124 0%, #0f1416 52%, #0a0c0d 100%)" }} />

      <div className="relative grid min-h-[calc(100svh-56px)] lg:block lg:h-[calc(100svh-56px)] lg:max-h-[1000px] lg:min-h-[640px]">
        <div ref={host} className={`relative h-[58svh] min-h-[340px] transition-opacity duration-700 ease-out lg:absolute lg:inset-0 lg:h-auto ${ready ? "opacity-100" : "opacity-0"}`}
          role="img" aria-label="Point cloud of the public advisories with a nearest-neighbour graph. Drag to turn it." />
        <div aria-hidden className="hero-vignette pointer-events-none lg:inset-0" />
        <div aria-hidden className="hero-grain pointer-events-none" />
        <div ref={label} aria-hidden className="pointer-events-none absolute top-0 left-0 opacity-0 transition-opacity duration-300">
          <span className="ml-3 -translate-y-1/2 inline-block whitespace-nowrap rounded-[3px] bg-paper px-1.5 py-[1px] font-mono text-[11px] font-semibold text-ink">your question</span>
        </div>
        {heroErr && (
          <p className="absolute top-6 left-6 max-w-[60ch] text-sm text-slab-mute" data-testid="hero-fallback">
            {heroErr.kind === "webgl"
              ? "The 3D view needs WebGL; everything below works without it."
              : `Could not load the corpus map (${heroErr.message}); everything below works without it.`}
          </p>
        )}

        <div className={`pointer-events-none relative z-10 mx-auto flex max-w-[1600px] flex-col justify-end gap-8 px-4 pb-10 transition-opacity duration-300 ease-out sm:px-6 lg:h-full lg:px-8 lg:pb-14 ${chapter ? "lg:opacity-0" : ""}`}
          style={chapter ? { visibility: "hidden" } : undefined}>
          <div className="pointer-events-auto hidden max-w-[40ch] lg:absolute lg:top-8 lg:block">
            <p className="font-mono text-[11px] leading-4 text-slab-mute">
              {info ? `${fmt.int(info.n)} public advisories (${fmt.int(info.excluded_embargoed)} embargoed rows left out), each placed by its meaning (nomic-embed-text, 768 dimensions to 3D by PCA). The faint lines link near neighbours; the pulses walk them toward the question, the way a DiskANN index search moves (an illustration). Drag to turn.` : "\u00a0"}
            </p>
            <button onClick={() => setPaused(!paused)} aria-pressed={paused} data-testid="pause-motion"
              className="btn btn-ghost-dark mt-3 min-h-0 px-2.5 py-1 text-xs font-medium">
              {paused ? "Play motion" : "Pause motion"}
            </button>
          </div>
          <div className="grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_400px]">
            <div className="pointer-events-auto">
              <h1 className="font-display text-[clamp(3.4rem,8.6vw,8.75rem)] leading-[0.86] font-semibold tracking-[-0.045em]">
                Find the<br />needle.
              </h1>
              <p className="mt-6 max-w-[48ch] text-[17px] leading-7 text-[#c9d2d5]">
                Vulnerability triage inside IBM Db2. Paste a vague advisory: one SQL statement finds it by keyword and by
                meaning, row access control decides what you may see, and a temporal SBOM join names the services it hits.
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-5">
                <a href="#/triage" className="btn btn-primary no-underline" data-testid="hero-cta">Open the triage console</a>
                <a href="#/finding" className="text-sm text-[#9fe3e8] hover:text-paper">Read the finding</a>
              </div>
            </div>
            {info && query && readout && (
              <div className="pointer-events-auto rounded-[6px] border border-slab-rule bg-[#0e1213]/85 p-4 backdrop-blur-[2px]" data-testid="hero-controls">
                <Ctl label="Question" value={q} onChange={setQ} options={info.queries.map((x) => ({ value: x.key, label: QUERY_LABEL[x.key] ?? x.key }))} />
                <Ctl label="Seen by" value={who} onChange={setWho} options={[{ value: "all", label: "Full visibility" }, { value: "p10", label: "10% analyst" }]} />
                {who === "p10" && <Ctl label="Search" value={plan} onChange={setPlan} options={[{ value: "shared", label: "Shared plan" }, { value: "router", label: "NEEDLE router" }]} />}
                <div className="mt-3 border-t border-slab-rule pt-3" aria-live="polite">
                  <p className={`font-mono text-2xl font-semibold num ${readout.tone}`}>{readout.n} <span className="text-sm font-medium text-slab-mute">rows</span></p>
                  <p className="mt-1 text-[13px] leading-5 text-[#b7c1c4]">{readout.line}</p>
                </div>
              </div>
            )}
          </div>
        </div>
        {chapters.length > 0 && (chapter > 0 || leaving > 0) && (
          <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 z-10 hidden lg:block">
            <div className="absolute inset-0 -top-40 transition-opacity duration-300" style={{ opacity: chapter ? 1 : 0, background: "radial-gradient(70% 100% at 0% 100%, rgba(10,12,13,.92) 0%, rgba(10,12,13,.6) 45%, transparent 75%)" }} />
            <div className="relative mx-auto grid max-w-[1600px] px-8 pb-16">
              {leaving > 0 && leaving !== chapter && <ChapterText key={`out-${leaving}`} c={chapters[leaving - 1]} exit />}
              {chapter > 0 && <ChapterText key={`in-${chapter}`} c={chapters[chapter - 1]} cta={chapter === chapters.length} />}
            </div>
          </div>
        )}
        {chapters.length > 0 && (
          <ol ref={railRef} aria-label="Story chapters" className={`absolute top-1/2 right-8 z-20 hidden -translate-y-1/2 justify-items-end gap-5 transition-opacity duration-300 lg:grid ${chapter ? "opacity-100" : "pointer-events-none opacity-0"}`}>
            {chapters.map((c, i) => {
              const n = i + 1, on = chapter === n, done = chapter > n;
              return (
                <li key={c.name}>
                  <button onClick={() => jumpTo(n)} aria-current={on ? "step" : undefined} tabIndex={chapter ? 0 : -1}
                    className={`group flex items-center justify-end gap-4 text-right transition-colors duration-200 ${on ? "text-paper" : "text-slab-mute hover:text-[#dfe7e9]"}`}>
                    <span className="grid">
                      <span className={`font-mono text-[11px] transition-colors duration-200 ${on ? "text-[#9fe3e8]" : ""}`}>{n} / {chapters.length}</span>
                      <span className={`text-[15px] leading-6 transition-[font-weight,transform] duration-300 ${on ? "font-semibold" : "font-medium"}`}
                        style={{ transform: on ? "translateX(-4px)" : "none" }}>{c.name}</span>
                    </span>
                    <span className="relative h-[3px] w-14 overflow-hidden rounded-full bg-slab-rule">
                      <span className={`absolute inset-0 rounded-full ${on ? "rail-fill bg-accent" : done ? "bg-accent/45" : ""}`} />
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
      </div>
      <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:pointer-events-none lg:px-8" data-testid="story-chapters">
        {chapters.map((c) => (
          <article key={c.name} className="border-t border-slab-rule py-10 lg:flex lg:h-[100svh] lg:items-end lg:border-0 lg:py-0 lg:opacity-0">
            <div>
              <h2 className="font-display text-3xl font-semibold tracking-[-0.025em]">{c.title}</h2>
              <p className="mt-3 max-w-[52ch] text-md text-[#c9d2d5]">{c.body}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ChapterText({ c, exit = false, cta = false }: { c: { title: string; body: string }; exit?: boolean; cta?: boolean }) {
  const words = c.title.split(" ");
  return (
    <div className={`col-start-1 row-start-1 self-end ${exit ? "chapter-exit" : ""}`}>
      <h2 className="max-w-[16ch] font-display text-[clamp(2.6rem,4.6vw,4.6rem)] leading-[0.95] font-semibold tracking-[-0.035em]">
        {words.map((w, i) => (
          <Fragment key={i}>
            <span className="word-mask"><span className={exit ? "" : "word-rise"} style={{ ["--i" as string]: i }}>{w}</span></span>
            {i < words.length - 1 ? " " : ""}
          </Fragment>
        ))}
      </h2>
      <p className={`mt-5 max-w-[52ch] text-[17px] leading-7 text-[#c9d2d5] ${exit ? "" : "fade-up"}`} style={{ ["--d" as string]: `${0.36 + words.length * 0.055}s` }}>{c.body}</p>
      {cta && <a href="#/triage" className={`btn btn-primary pointer-events-auto mt-7 no-underline ${exit ? "" : "fade-up"}`} style={{ ["--d" as string]: `${0.5 + words.length * 0.055}s` }}>Open the triage console</a>}
    </div>
  );
}

function Ctl<T extends string>({ label, value, onChange, options }: { label: string; value: T; onChange: (v: T) => void; options: { value: T; label: string }[] }) {
  return (
    <div className="mt-2 grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-2 first:mt-0">
      <span className="text-xs text-slab-mute">{label}</span>
      <div role="radiogroup" aria-label={label} className="flex rounded-[5px] border border-slab-rule p-0.5">
        {options.map((o) => (
          <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
            className={`min-h-8 flex-1 rounded-[3px] px-2 text-[12.5px] font-medium whitespace-nowrap transition-colors duration-150 ${value === o.value ? "bg-paper text-ink" : "text-[#c9d2d5] hover:bg-slab-2"}`}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

function FindingTeaser() {
  const [f, setF] = useState<Finding | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.finding().then(setF).catch((e) => setErr(errText(e))); }, []);
  const p10 = f?.selectivity?.series?.rcac?.[0], r10 = f?.selectivity?.series?.router?.[0];
  if (err || (f && (!p10 || !r10))) {
    return (
      <p role="status" title={err ?? "The finding has no selectivity series"} className="border-b border-hair py-6 text-sm text-mute" data-testid="finding-teaser-error">
        Could not load the measured results from the local API.
      </p>
    );
  }
  if (!f || !p10 || !r10) return null;
  return (
    <section className="grid gap-10 border-b border-hair py-16 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-16 lg:py-24">
      <div>
        <h2 className="font-display text-[clamp(2.6rem,5vw,4.5rem)] leading-[0.95] font-semibold tracking-[-0.035em]">
          Ask Db2 for 10.<br />Get <span className="text-affected">{Math.round(p10.rows)}</span>.
        </h2>
        <p className="mt-5 max-w-[56ch] text-md text-ink-2">
          Under row access control every analyst shares one plan, and that plan sizes the vector index's first batch as
          if everyone could see about half the rows. An analyst who sees {Math.round(p10.x)}% asks for 10 and gets about{" "}
          {Math.round(p10.rows)}. NEEDLE measured it, found the cause, and routes around it.
        </p>
        <a href="#/finding" className="mt-5 inline-block text-sm">Read the finding</a>
      </div>
      <dl className="grid grid-cols-2 content-end gap-x-8 gap-y-6">
        <Big value={fmt.dec(p10.recall)} label={`recall@10 at ${Math.round(p10.x)}% visible, shared plan`} red />
        <Big value={fmt.dec(r10.recall)} label="same analyst, NEEDLE router" />
        <Big value={fmt.dec(f.estimate.permission_ff)} label="the one permission estimate, every user" />
        <Big value={`${f.correlated.p10_zero_rows} / ${f.correlated.queries}`} label="queries with no rows when visibility follows topics" red />
      </dl>
    </section>
  );
}

function Big({ value, label, red }: { value: string; label: string; red?: boolean }) {
  return (
    <div className="border-t border-ink pt-3">
      <dd className={`font-mono text-3xl font-semibold num ${red ? "text-affected" : "text-ink"}`}>{value}</dd>
      <dt className="mt-1 text-xs text-mute">{label}</dt>
    </div>
  );
}
