// Pure condition-tree helpers for the visual strategy builder (vitest-covered).

export interface Operand {
  kind: "indicator" | "price" | "const";
  ref?: string;
  output?: string;
  field?: "open" | "high" | "low" | "close";
  value?: number;
  offsetBars?: number;
}

export interface Condition {
  id: string;
  left: Operand;
  op: ">" | ">=" | "<" | "<=" | "==" | "!=" | "crossesAbove" | "crossesBelow";
  right: Operand;
}

export interface Group {
  id: string;
  group: "all" | "any";
  children: Node[];
}

export type Node = Condition | Group;

export function isGroup(n: Node): n is Group {
  return "group" in n;
}

let counter = 0;
export function freshId(prefix: string): string {
  counter += 1;
  return `${prefix}${Date.now().toString(36)}${counter}`;
}
export function resetIds(): void {
  counter = 0;
}

export function newLeaf(): Condition {
  return {
    id: freshId("c"),
    left: { kind: "price", field: "close" },
    op: ">",
    right: { kind: "const", value: 0 },
  };
}

export function newGroupNode(logic: "all" | "any" = "any"): Group {
  return { id: freshId("g"), group: logic, children: [newLeaf()] };
}

export function countLeaves(nodes: Node[]): number {
  return nodes.reduce((n, x) => n + (isGroup(x) ? countLeaves(x.children) : 1), 0);
}

export function maxDepth(nodes: Node[], depth = 1): number {
  let m = depth;
  for (const x of nodes) {
    if (isGroup(x)) m = Math.max(m, maxDepth(x.children, depth + 1));
  }
  return m;
}

/** Immutable update: apply fn to the node with id, return new tree. */
export function updateTree(nodes: Node[], id: string, fn: (n: Node) => Node): Node[] {
  return nodes.map((n) => {
    if (n.id === id) return fn(n);
    if (isGroup(n)) return { ...n, children: updateTree(n.children, id, fn) };
    return n;
  });
}

/** Immutable remove by id (leaf or group). */
export function removeNode(nodes: Node[], id: string): Node[] {
  const out: Node[] = [];
  for (const n of nodes) {
    if (n.id === id) continue;
    out.push(isGroup(n) ? { ...n, children: removeNode(n.children, id) } : n);
  }
  return out;
}

/** Immutable insert into group (or top level when parentId is null). */
export function insertNode(nodes: Node[], parentId: string | null, node: Node): Node[] {
  if (parentId === null) return [...nodes, node];
  return nodes.map((n) => {
    if (n.id === parentId && isGroup(n)) return { ...n, children: [...n.children, node] };
    if (isGroup(n)) return { ...n, children: insertNode(n.children, parentId, node) };
    return n;
  });
}

/** Human-readable one-liner for a node (also used by rule display). */
export function describeNode(n: Node): string {
  if (isGroup(n)) {
    const joiner = n.group === "all" ? " AND " : " OR ";
    return `(${n.children.map(describeNode).join(joiner)})`;
  }
  return `${describeOperand(n.left)} ${n.op} ${describeOperand(n.right)}`;
}

export function describeOperand(op: Operand): string {
  if (op.kind === "const") return String(op.value ?? 0);
  if (op.kind === "price") {
    const base = op.field ?? "close";
    return op.offsetBars ? `${base}[${op.offsetBars}]` : base;
  }
  const base = op.ref ?? "?";
  const out = op.output ? `.${op.output}` : "";
  const off = op.offsetBars ? `[${op.offsetBars}]` : "";
  return `${base}${out}${off}`;
}
