import { CONDITION_OPS, PRICE_FIELDS } from "../generated/enums";
import {
  describeNode,
  insertNode,
  isGroup,
  maxDepth,
  countLeaves,
  newGroupNode,
  newLeaf,
  removeNode,
  updateTree,
  type Condition,
  type Group,
  type Node,
  type Operand,
} from "../conditions";

interface Indicator {
  id: string;
  kind: string;
}

const OUTPUTS: Record<string, string[]> = {
  MACD: ["macd", "signal", "histogram"],
  BB: ["upper", "middle", "lower"],
  Donchian: ["upper", "lower", "middle"],
};

function OperandEditor({
  op,
  indicators,
  onChange,
}: {
  op: Operand;
  indicators: Indicator[];
  onChange: (op: Operand) => void;
}) {
  return (
    <span className="row" style={{ display: "inline-flex" }}>
      <select value={op.kind} onChange={(e) => {
        const kind = e.target.value as Operand["kind"];
        if (kind === "const") onChange({ kind, value: 0 });
        else if (kind === "price") onChange({ kind, field: "close" });
        else onChange({ kind, ref: indicators[0]?.id ?? "" });
      }}>
        <option value="indicator">indicator</option>
        <option value="price">price</option>
        <option value="const">number</option>
      </select>
      {op.kind === "indicator" && (
        <>
          <select value={op.ref ?? ""} onChange={(e) => onChange({ ...op, ref: e.target.value, output: undefined })}>
            {indicators.map((i) => (
              <option key={i.id} value={i.id}>
                {i.id} ({i.kind})
              </option>
            ))}
          </select>
          {(() => {
            const kind = indicators.find((i) => i.id === op.ref)?.kind;
            const outs = kind ? OUTPUTS[kind] : undefined;
            if (!outs) return null;
            return (
              <select value={op.output ?? ""} onChange={(e) => onChange({ ...op, output: e.target.value || undefined })}>
                <option value="">— output —</option>
                {outs.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            );
          })()}
          <input
            type="number"
            min={0}
            placeholder="offset"
            title="offsetBars (0 = just-closed)"
            value={op.offsetBars ?? 0}
            onChange={(e) => onChange({ ...op, offsetBars: Number(e.target.value) })}
            style={{ width: 70 }}
          />
        </>
      )}
      {op.kind === "price" && (
        <>
          <select value={op.field ?? "close"} onChange={(e) => onChange({ ...op, field: e.target.value as Operand["field"] })}>
            {PRICE_FIELDS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            placeholder="offset"
            title="offsetBars (0 = just-closed)"
            value={op.offsetBars ?? 0}
            onChange={(e) => onChange({ ...op, offsetBars: Number(e.target.value) })}
            style={{ width: 70 }}
          />
        </>
      )}
      {op.kind === "const" && (
        <input type="number" step="any" value={op.value ?? 0} onChange={(e) => onChange({ ...op, value: Number(e.target.value) })} style={{ width: 90 }} />
      )}
    </span>
  );
}

function NodeEditor({ node, indicators, onChange, onRemove }: {
  node: Node;
  indicators: Indicator[];
  onChange: (n: Node) => void;
  onRemove: () => void;
}) {
  if (isGroup(node)) {
    return (
      <div className="cond-tree">
        <span className="cond-group-label">
          {node.group === "all" ? "ALL of" : "ANY of"}
          <select value={node.group} onChange={(e) => onChange({ ...node, group: e.target.value as Group["group"] })} style={{ marginLeft: 8 }}>
            <option value="all">ALL</option>
            <option value="any">ANY</option>
          </select>
          <button className="mini-btn danger" onClick={onRemove} style={{ marginLeft: 8 }}>
            remove group
          </button>
        </span>
        {node.children.map((c) => (
          <NodeEditor
            key={c.id}
            node={c}
            indicators={indicators}
            onChange={(n) => onChange({ ...node, children: node.children.map((x) => (x.id === c.id ? n : x)) })}
            onRemove={() => onChange({ ...node, children: node.children.filter((x) => x.id !== c.id) })}
          />
        ))}
      </div>
    );
  }
  return (
    <div className="cond-leaf">
      <OperandEditor op={node.left} indicators={indicators} onChange={(op) => onChange({ ...node, left: op })} />
      <select value={node.op} onChange={(e) => onChange({ ...node, op: e.target.value as Condition["op"] })}>
        {CONDITION_OPS.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <OperandEditor op={node.right} indicators={indicators} onChange={(op) => onChange({ ...node, right: op })} />
      <button className="mini-btn danger" onClick={onRemove}>
        ✕
      </button>
    </div>
  );
}

export function ConditionBuilder({
  nodes,
  indicators,
  onChange,
}: {
  nodes: Node[];
  indicators: Indicator[];
  onChange: (nodes: Node[]) => void;
}) {
  const leaves = countLeaves(nodes);
  const depth = maxDepth(nodes);
  return (
    <div>
      <p className="muted">
        {describeNode({ id: "top", group: "all", children: nodes })} · {leaves}/12 conditions · depth {depth}/3
      </p>
      {nodes.map((n) => (
        <NodeEditor
          key={n.id}
          node={n}
          indicators={indicators}
          onChange={(next) => onChange(updateTree(nodes, n.id, () => next))}
          onRemove={() => onChange(removeNode(nodes, n.id))}
        />
      ))}
      <div className="row">
        <button className="mini-btn" onClick={() => onChange(insertNode(nodes, null, newLeaf()))}>
          + condition
        </button>
        <button className="mini-btn" onClick={() => onChange(insertNode(nodes, null, newGroupNode("any")))}>
          + group (OR)
        </button>
        <button className="mini-btn" onClick={() => onChange(insertNode(nodes, null, newGroupNode("all")))}>
          + group (AND)
        </button>
      </div>
    </div>
  );
}
