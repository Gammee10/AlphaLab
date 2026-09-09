import { describe, expect, it } from "vitest";
import {
  countLeaves,
  describeNode,
  insertNode,
  maxDepth,
  newGroupNode,
  newLeaf,
  removeNode,
  resetIds,
  updateTree,
} from "./conditions";

describe("condition tree", () => {
  it("counts leaves and depth", () => {
    resetIds();
    const tree = [newLeaf(), { ...newGroupNode("any"), children: [newLeaf(), newLeaf()] }];
    expect(countLeaves(tree)).toBe(3);
    expect(maxDepth(tree)).toBe(2);
    expect(maxDepth([newLeaf()])).toBe(1);
  });

  it("updates, inserts, removes immutably", () => {
    resetIds();
    const leaf = newLeaf();
    const updated = updateTree([leaf], leaf.id, (n) => ({ ...n, op: "<" as const }));
    expect(updated[0]).toMatchObject({ op: "<" });
    expect(leaf.op).toBe(">");
    const group = newGroupNode("all");
    const withChild = insertNode([], null, group);
    expect(withChild).toHaveLength(1);
    const nested = insertNode(withChild, group.id, newLeaf());
    expect(countLeaves(nested)).toBe(2);
    const removed = removeNode(nested, group.children[0].id);
    expect(countLeaves(removed)).toBe(1);
    expect(removeNode(nested, group.id)).toEqual([]);
  });

  it("describes nodes", () => {
    resetIds();
    expect(describeNode(newLeaf())).toBe("close > 0");
    const g = { ...newGroupNode("all"), children: [newLeaf(), newLeaf()] };
    expect(describeNode(g)).toBe("(close > 0 AND close > 0)");
  });
});
