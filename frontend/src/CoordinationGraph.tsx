import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { CoordinationGraphData, CoordinationGraphNode } from "./types";

const WIDTH = 760;
const HEIGHT = 440;
const COLORS = [
  "#16776a",
  "#b27625",
  "#895f9e",
  "#4677a8",
  "#9f4d44",
  "#557d46",
];
const MIN_ZOOM = 0.55;
const MAX_ZOOM = 2.4;

type Point = { x: number; y: number };
type PositionedNode = CoordinationGraphNode & Point;
type Viewport = Point & { scale: number };
type DragState =
  | { kind: "node"; id: string; pointerId: number; offset: Point }
  | { kind: "canvas"; pointerId: number; start: Point; viewport: Viewport };

const clamp = (value: number, minimum: number, maximum: number) =>
  Math.max(minimum, Math.min(maximum, value));

function positions(data: CoordinationGraphData): Map<string, PositionedNode> {
  const groups = new Map<string, CoordinationGraphNode[]>();
  for (const node of data.nodes) {
    const key =
      node.cluster_id === null
        ? `isolated-${node.id}`
        : `cluster-${node.cluster_id}`;
    groups.set(key, [...(groups.get(key) ?? []), node]);
  }
  const entries = [...groups.entries()];
  const result = new Map<string, PositionedNode>();
  entries.forEach(([, members], groupIndex) => {
    const groupAngle =
      (2 * Math.PI * groupIndex) / Math.max(1, entries.length) - Math.PI / 2;
    const groupRadius =
      entries.length === 1 ? 0 : Math.min(145, 45 * entries.length);
    const centerX = WIDTH / 2 + Math.cos(groupAngle) * groupRadius;
    const centerY = HEIGHT / 2 + Math.sin(groupAngle) * groupRadius;
    const memberRadius =
      members.length === 1 ? 0 : Math.min(108, 30 + members.length * 5);
    members.forEach((node, memberIndex) => {
      const angle =
        (2 * Math.PI * memberIndex) / Math.max(1, members.length) - Math.PI / 2;
      result.set(node.id, {
        ...node,
        x: centerX + Math.cos(angle) * memberRadius,
        y: centerY + Math.sin(angle) * memberRadius,
      });
    });
  });
  return result;
}

function arrangeNodes(
  data: CoordinationGraphData,
  current: Map<string, PositionedNode>,
  pinned: Set<string>,
): Record<string, Point> {
  const working = new Map(
    [...current].map(([id, node]) => [id, { x: node.x, y: node.y }]),
  );
  const edgeByNode = new Map<
    string,
    Array<{ other: string; strength: number }>
  >();
  for (const edge of data.edges) {
    edgeByNode.set(edge.source, [
      ...(edgeByNode.get(edge.source) ?? []),
      { other: edge.target, strength: edge.strength },
    ]);
    edgeByNode.set(edge.target, [
      ...(edgeByNode.get(edge.target) ?? []),
      { other: edge.source, strength: edge.strength },
    ]);
  }

  for (let iteration = 0; iteration < 90; iteration += 1) {
    const next = new Map(working);
    for (const [id, point] of working) {
      if (pinned.has(id)) continue;
      let forceX = (WIDTH / 2 - point.x) * 0.004;
      let forceY = (HEIGHT / 2 - point.y) * 0.004;
      for (const [otherId, other] of working) {
        if (otherId === id) continue;
        const dx = other.x - point.x;
        const dy = other.y - point.y;
        const distance = Math.max(12, Math.hypot(dx, dy));
        const repulsion = 3200 / (distance * distance);
        forceX -= (dx / distance) * repulsion;
        forceY -= (dy / distance) * repulsion;
      }
      for (const edge of edgeByNode.get(id) ?? []) {
        const other = working.get(edge.other);
        if (!other) continue;
        const dx = other.x - point.x;
        const dy = other.y - point.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const spring = (distance - 82) * 0.012 * edge.strength;
        forceX += (dx / distance) * spring;
        forceY += (dy / distance) * spring;
      }
      next.set(id, {
        x: clamp(point.x + forceX * 0.55, 24, WIDTH - 24),
        y: clamp(point.y + forceY * 0.55, 24, HEIGHT - 24),
      });
    }
    working.clear();
    for (const [id, point] of next) working.set(id, point);
  }
  return Object.fromEntries(working);
}

function nodeColor(node: CoordinationGraphNode): string {
  return node.cluster_id === null
    ? "#98aaa5"
    : COLORS[(node.cluster_id - 1) % COLORS.length];
}

export default function CoordinationGraph({ postId }: { postId: string }) {
  const graph = useQuery({
    queryKey: ["coordination-graph", postId],
    queryFn: () => api.coordinationGraph(postId),
  });
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [moved, setMoved] = useState<Record<string, Point>>({});
  const [pinned, setPinned] = useState<Set<string>>(new Set());
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, scale: 1 });
  const [dragMode, setDragMode] = useState<"idle" | "node" | "canvas">("idle");
  const baseLayout = useMemo(
    () =>
      graph.data ? positions(graph.data) : new Map<string, PositionedNode>(),
    [graph.data],
  );
  const layout = useMemo(() => {
    const result = new Map<string, PositionedNode>();
    for (const [id, node] of baseLayout)
      result.set(id, { ...node, ...(moved[id] ?? {}) });
    return result;
  }, [baseLayout, moved]);

  const svgPoint = (clientX: number, clientY: number): Point => {
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds || bounds.width === 0 || bounds.height === 0)
      return { x: 0, y: 0 };
    return {
      x: ((clientX - bounds.left) / bounds.width) * WIDTH,
      y: ((clientY - bounds.top) / bounds.height) * HEIGHT,
    };
  };
  const graphPoint = (clientX: number, clientY: number): Point => {
    const point = svgPoint(clientX, clientY);
    return {
      x: (point.x - viewport.x) / viewport.scale,
      y: (point.y - viewport.y) / viewport.scale,
    };
  };
  const zoomAt = (nextScale: number, anchor: Point) => {
    setViewport((current) => {
      const scale = clamp(nextScale, MIN_ZOOM, MAX_ZOOM);
      const graphX = (anchor.x - current.x) / current.scale;
      const graphY = (anchor.y - current.y) / current.scale;
      return {
        x: anchor.x - graphX * scale,
        y: anchor.y - graphY * scale,
        scale,
      };
    });
  };
  const moveNode = (id: string, point: Point) => {
    setMoved((current) => ({
      ...current,
      [id]: {
        x: clamp(point.x, 18, WIDTH - 18),
        y: clamp(point.y, 18, HEIGHT - 18),
      },
    }));
    setPinned((current) => new Set(current).add(id));
  };
  const togglePin = (id: string) => {
    setPinned((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const endDrag = () => {
    dragRef.current = null;
    setDragMode("idle");
  };

  if (graph.error)
    return (
      <section className="panel graph-panel">
        <h2>Coordination graph unavailable</h2>
        <p className="error">{graph.error.message}</p>
      </section>
    );
  if (!graph.data)
    return (
      <section className="panel graph-panel">
        <h2>Coordination graph</h2>
        <p className="muted">Building behavioral connections…</p>
      </section>
    );

  const data = graph.data;
  const selected =
    data.nodes.find((node) => node.id === selectedId) ?? data.nodes[0];
  const selectedEdges = selected
    ? data.edges
        .filter(
          (edge) => edge.source === selected.id || edge.target === selected.id,
        )
        .sort((left, right) => right.strength - left.strength)
        .slice(0, 5)
    : [];
  const byId = new Map(data.nodes.map((node) => [node.id, node]));

  return (
    <section
      className="panel graph-panel"
      aria-labelledby={`graph-title-${postId}`}
    >
      <div className="graph-heading">
        <div>
          <p className="eyebrow">Behavioral relationships</p>
          <h2 id={`graph-title-${postId}`}>Coordination graph</h2>
          <p>
            Connections combine repeated text, close timing, shared reply
            targets
            {data.method.semantic_context_available
              ? ", and experimental semantic context"
              : ""}
            .
          </p>
        </div>
        <div className="graph-summary" aria-label="Graph summary">
          <span>
            <strong>{data.summary.participant_count_shown}</strong> participants
          </span>
          <span>
            <strong>{data.summary.edge_count}</strong> connections
          </span>
          <span>
            <strong>{data.summary.cluster_count}</strong> clusters
          </span>
        </div>
      </div>
      {data.nodes.length === 0 ? (
        <p className="muted">
          No participant activity is available for this post.
        </p>
      ) : (
        <>
          <div className="graph-toolbar" aria-label="Graph controls">
            <button
              type="button"
              className="secondary"
              onClick={() => setMoved(arrangeNodes(data, layout, pinned))}
            >
              Arrange nodes
            </button>
            <button
              type="button"
              className="secondary icon-button"
              aria-label="Zoom out"
              onClick={() =>
                zoomAt(viewport.scale / 1.2, { x: WIDTH / 2, y: HEIGHT / 2 })
              }
            >
              −
            </button>
            <output aria-label="Current zoom">
              {Math.round(viewport.scale * 100)}%
            </output>
            <button
              type="button"
              className="secondary icon-button"
              aria-label="Zoom in"
              onClick={() =>
                zoomAt(viewport.scale * 1.2, { x: WIDTH / 2, y: HEIGHT / 2 })
              }
            >
              +
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setMoved({});
                setPinned(new Set());
                setViewport({ x: 0, y: 0, scale: 1 });
              }}
            >
              Reset layout
            </button>
            <span>
              Drag nodes · drag canvas to pan · wheel or trackpad to zoom
            </span>
          </div>
          <div className="graph-layout">
            <div
              className={`graph-canvas ${dragMode}`}
              aria-label="Interactive participant coordination graph"
            >
              <svg
                ref={svgRef}
                viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                role="application"
                aria-label="Movable pseudonymous participant graph"
                onPointerDown={(event) => {
                  const start = svgPoint(event.clientX, event.clientY);
                  dragRef.current = {
                    kind: "canvas",
                    pointerId: event.pointerId,
                    start,
                    viewport,
                  };
                  event.currentTarget.setPointerCapture(event.pointerId);
                  setDragMode("canvas");
                }}
                onPointerMove={(event) => {
                  const drag = dragRef.current;
                  if (!drag || drag.pointerId !== event.pointerId) return;
                  if (drag.kind === "node") {
                    const point = graphPoint(event.clientX, event.clientY);
                    moveNode(drag.id, {
                      x: point.x + drag.offset.x,
                      y: point.y + drag.offset.y,
                    });
                  } else {
                    const point = svgPoint(event.clientX, event.clientY);
                    setViewport({
                      ...drag.viewport,
                      x: drag.viewport.x + point.x - drag.start.x,
                      y: drag.viewport.y + point.y - drag.start.y,
                    });
                  }
                }}
                onPointerUp={endDrag}
                onPointerCancel={endDrag}
                onWheel={(event) => {
                  event.preventDefault();
                  const anchor = svgPoint(event.clientX, event.clientY);
                  zoomAt(
                    viewport.scale * (event.deltaY > 0 ? 0.9 : 1.1),
                    anchor,
                  );
                }}
              >
                <title>
                  Movable pseudonymous participant coordination graph
                </title>
                <g
                  transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}
                >
                  <g className="graph-edges">
                    {data.edges.map((edge) => {
                      const source = layout.get(edge.source);
                      const target = layout.get(edge.target);
                      if (!source || !target) return null;
                      return (
                        <line
                          key={edge.id}
                          x1={source.x}
                          y1={source.y}
                          x2={target.x}
                          y2={target.y}
                          strokeWidth={1 + edge.strength * 5}
                          className={
                            selected &&
                            (edge.source === selected.id ||
                              edge.target === selected.id)
                              ? "selected"
                              : ""
                          }
                        >
                          <title>{`${Math.round(edge.strength * 100)}% connection: ${edge.reasons.join(", ")}`}</title>
                        </line>
                      );
                    })}
                  </g>
                  <g className="graph-nodes">
                    {[...layout.values()].map((node) => {
                      const radius = 10 + Math.min(7, node.event_count * 1.5);
                      const isPinned = pinned.has(node.id);
                      return (
                        <g
                          key={node.id}
                          role="button"
                          tabIndex={0}
                          aria-label={`${node.label}, ${node.connection_count} connections${isPinned ? ", pinned" : ""}`}
                          aria-pressed={selected?.id === node.id}
                          className={`${selected?.id === node.id ? "selected" : ""} ${isPinned ? "pinned" : ""}`}
                          onPointerDown={(event) => {
                            event.stopPropagation();
                            const point = graphPoint(
                              event.clientX,
                              event.clientY,
                            );
                            dragRef.current = {
                              kind: "node",
                              id: node.id,
                              pointerId: event.pointerId,
                              offset: {
                                x: node.x - point.x,
                                y: node.y - point.y,
                              },
                            };
                            setSelectedId(node.id);
                            setDragMode("node");
                          }}
                          onDoubleClick={(event) => {
                            event.stopPropagation();
                            togglePin(node.id);
                          }}
                          onClick={() => setSelectedId(node.id)}
                          onKeyDown={(event) => {
                            const delta: Record<string, Point> = {
                              ArrowLeft: { x: -8, y: 0 },
                              ArrowRight: { x: 8, y: 0 },
                              ArrowUp: { x: 0, y: -8 },
                              ArrowDown: { x: 0, y: 8 },
                            };
                            if (delta[event.key]) {
                              event.preventDefault();
                              moveNode(node.id, {
                                x: node.x + delta[event.key].x,
                                y: node.y + delta[event.key].y,
                              });
                            } else if (
                              event.key === "Enter" ||
                              event.key === " "
                            ) {
                              event.preventDefault();
                              setSelectedId(node.id);
                            }
                          }}
                        >
                          <circle
                            cx={node.x}
                            cy={node.y}
                            r={radius}
                            fill={nodeColor(node)}
                          />
                          {isPinned && (
                            <circle
                              className="pin-dot"
                              cx={node.x + radius - 2}
                              cy={node.y - radius + 2}
                              r={4}
                            />
                          )}
                          <text
                            x={node.x}
                            y={node.y + radius + 14}
                            textAnchor="middle"
                          >
                            {node.label.replace("Participant ", "")}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </g>
              </svg>
            </div>
            {selected && (
              <aside className="graph-inspector" aria-live="polite">
                <span className="pill">
                  {selected.cluster_id === null
                    ? "not clustered"
                    : `cluster ${selected.cluster_id}`}
                </span>
                <h3>{selected.label}</h3>
                <p className="graph-pin-status">
                  {pinned.has(selected.id)
                    ? "Position pinned"
                    : "Drag to move and pin"}
                </p>
                <dl>
                  <div>
                    <dt>Events</dt>
                    <dd>{selected.event_count}</dd>
                  </div>
                  <div>
                    <dt>Replies</dt>
                    <dd>{selected.reply_count}</dd>
                  </div>
                  <div>
                    <dt>Connections</dt>
                    <dd>{selected.connection_count}</dd>
                  </div>
                  <div>
                    <dt>Average strength</dt>
                    <dd>
                      {Math.round(selected.average_connection_strength * 100)}%
                    </dd>
                  </div>
                </dl>
                {Object.keys(selected.context_relations).length > 0 && (
                  <div className="graph-context-summary">
                    <h4>Reply context</h4>
                    <ul>
                      {Object.entries(selected.context_relations).map(
                        ([relation, count]) => (
                          <li key={relation}>
                            <strong>{relation.replaceAll("_", " ")}</strong>
                            <span>
                              {count} repl{count === 1 ? "y" : "ies"}
                            </span>
                          </li>
                        ),
                      )}
                    </ul>
                  </div>
                )}
                <h4>Strongest connections</h4>
                {selectedEdges.length ? (
                  <ul>
                    {selectedEdges.map((edge) => {
                      const otherId =
                        edge.source === selected.id ? edge.target : edge.source;
                      return (
                        <li key={edge.id}>
                          <strong>{byId.get(otherId)?.label}</strong>
                          <span>
                            {Math.round(edge.strength * 100)}% ·{" "}
                            {edge.reasons.join(" · ")}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="muted">No qualifying behavioral connections.</p>
                )}
              </aside>
            )}
          </div>
        </>
      )}
      <footer className="graph-legend">
        <span>
          <i className="cluster" /> Color groups connected participants
        </span>
        <span>
          <i className="edge" /> Thicker lines indicate stronger combined
          evidence
        </span>
        <span>
          <i className="pin" /> Gold dot means the visual position is pinned
        </span>
      </footer>
      {data.summary.truncated && (
        <p className="hint">
          Showing {data.summary.participant_count_shown} of{" "}
          {data.summary.participant_count_total} participants.
        </p>
      )}
      <p className="hint">
        Layout changes stay in this browser view and do not alter detection
        results.
      </p>
      {data.method.semantic_context_available && (
        <p className="hint">
          Semantic-context rankings compare meaning plus conversation context.
          They are not proof of coordination, automation, intent, or agreement.
        </p>
      )}
      <p className="hint">{data.method.safety_statement}</p>
    </section>
  );
}
