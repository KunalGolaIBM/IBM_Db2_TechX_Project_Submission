/* React Flow genealogy graph. Layout is deterministic: the backend assigns each node a "layer"
   (supplier → lot → batch depth → distribution hop); nodes in a layer are stacked vertically. */
import { memo, useMemo } from "react";
import { Background, Controls, Handle, MiniMap, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Boxes, Building2, Factory, Package, Store, Truck, Warehouse, Wheat } from "lucide-react";
import type { GraphEdge, GraphNode } from "@/types";
import { cn } from "@/lib/utils";

const TYPE_META: Record<string, { icon: typeof Boxes; color: string; name: string }> = {
  supplier: { icon: Building2, color: "text-sky-300", name: "Supplier" },
  lot: { icon: Wheat, color: "text-amber-300", name: "Ingredient lot" },
  intermediate: { icon: Boxes, color: "text-violet-300", name: "Intermediate batch" },
  finished: { icon: Package, color: "text-cyan-300", name: "Finished batch" },
  facility: { icon: Factory, color: "text-slate-300", name: "Facility" },
  warehouse: { icon: Warehouse, color: "text-indigo-300", name: "Warehouse" },
  distributor: { icon: Truck, color: "text-teal-300", name: "Distributor" },
  retailer: { icon: Store, color: "text-emerald-300", name: "Retailer" },
};

type Data = GraphNode & { selected?: boolean } & Record<string, unknown>;

const ChainNode = memo(({ data }: NodeProps<Node<Data>>) => {
  const meta = TYPE_META[data.type] ?? TYPE_META.lot;
  const Icon = meta.icon;
  return (
    <div className={cn("w-[190px] rounded-lg border bg-ink-850/95 px-2.5 py-2 text-left shadow-lg transition-colors",
      data.affected ? "border-red-500/60 shadow-[0_0_18px_-6px_rgba(239,68,68,.7)]" : "border-line",
      data.focus && "ring-2 ring-cyan-400/70", data.selected && "border-cyan-400")}>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-slate-500" />
      <div className="flex items-center gap-1.5">
        <Icon className={cn("size-3.5 shrink-0", meta.color)} />
        <span className="truncate text-[11px] font-semibold text-slate-100">{data.label}</span>
        {data.affected && <span className="ml-auto size-1.5 shrink-0 rounded-full bg-red-400" aria-label="affected" />}
      </div>
      <p className="mt-0.5 truncate text-[10px] text-slate-400">{data.subtitle || meta.name}</p>
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-slate-500" />
    </div>
  );
});
ChainNode.displayName = "ChainNode";
const nodeTypes = { chain: ChainNode };

export function SupplyGraph({ nodes, edges, selected, onSelect, height = 560 }: { nodes: GraphNode[]; edges: GraphEdge[]; selected?: string | null; onSelect?: (n: GraphNode) => void; height?: number }) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const byLayer = new Map<number, GraphNode[]>();
    nodes.forEach((n) => byLayer.set(n.layer, [...(byLayer.get(n.layer) ?? []), n]));
    const layers = [...byLayer.keys()].sort((a, b) => a - b);
    const maxRows = Math.max(...[...byLayer.values()].map((l) => l.length), 1);
    // tall layers (e.g. 19 retailers) wrap into sub-columns so fitView keeps nodes legible
    const MAX_ROWS = 12;
    const rows = Math.min(maxRows, MAX_ROWS);
    const rfNodes: Node<Data>[] = [];
    let x = 0;
    layers.forEach((layer) => {
      const list = byLayer.get(layer)!.sort((a, b) => Number(b.affected) - Number(a.affected) || a.id.localeCompare(b.id));
      const cols = Math.ceil(list.length / MAX_ROWS);
      for (let c = 0; c < cols; c++) {
        const chunk = list.slice(c * MAX_ROWS, (c + 1) * MAX_ROWS);
        const offset = ((rows - chunk.length) * 60) / 2;
        chunk.forEach((n, row) => rfNodes.push({ id: n.id, type: "chain", position: { x: x + c * 205, y: offset + row * 60 }, data: { ...n, selected: n.id === selected } }));
      }
      x += cols * 205 + 25;
    });
    const rfEdges: Edge[] = edges.map((e) => ({
      id: e.id, source: e.source, target: e.target, label: e.kind === "supplies" ? undefined : e.label,
      animated: e.affected && e.kind === "ship",
      style: { stroke: e.affected ? "#f87171" : e.record_status && e.record_status !== "VERIFIED" ? "#fbbf24" : e.kind === "ship" ? "#2dd4bf55" : "#64748b", strokeWidth: e.affected ? 1.8 : 1.1, strokeDasharray: e.record_status && e.record_status !== "VERIFIED" ? "5 4" : e.status === "IN_TRANSIT" ? "2 4" : undefined },
      labelStyle: { fill: "#94a3b8", fontSize: 9 }, labelBgStyle: { fill: "#0a1222" }, labelBgPadding: [3, 1],
    }));
    return { rfNodes, rfEdges };
  }, [nodes, edges, selected]);

  return (
    <div style={{ height }} className="w-full overflow-hidden rounded-lg border border-line bg-ink-950/60" data-testid="supply-graph">
      <ReactFlow nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.04 }} minZoom={0.15} maxZoom={1.6} nodesDraggable={false}
        onNodeClick={(_, n) => onSelect?.(n.data as unknown as GraphNode)} proOptions={{ hideAttribution: true }}>
        <Background color="#1e293b" gap={22} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={(n) => ((n.data as unknown as Data).affected ? "#ef4444" : "#334155")} maskColor="rgba(6,11,22,.7)" />
      </ReactFlow>
    </div>
  );
}

export function GraphLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-slate-400">
      {Object.entries(TYPE_META).filter(([k]) => k !== "facility").map(([k, m]) => (
        <span key={k} className="inline-flex items-center gap-1"><m.icon className={cn("size-3.5", m.color)} />{m.name}</span>
      ))}
      <span className="inline-flex items-center gap-1"><span className="h-0.5 w-4 bg-red-400" />Affected</span>
      <span className="inline-flex items-center gap-1"><span className="h-0 w-4 border-t border-dashed border-amber-400" />Unverified record</span>
      <span className="inline-flex items-center gap-1"><span className="h-0 w-4 border-t border-dotted border-teal-300" />In transit</span>
    </div>
  );
}
