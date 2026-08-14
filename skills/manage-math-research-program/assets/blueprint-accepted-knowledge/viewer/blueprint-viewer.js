const SVG_NS = "http://www.w3.org/2000/svg";

const TYPE_ORDER = [
  "problem_hypothesis",
  "definition_contract",
  "external_mathematical_result",
  "mathematical_claim",
  "mathematical_inference",
  "verified_counterexample",
  "research_goal",
  "proof_obligation",
  "research_attempt",
  "basic_assumption",
  "theory_from_assumptions",
  "numerical_method",
  "numerical_result",
  "numerical_experiment_design",
  "theory_from_numerics",
  "superseded",
];

const TYPE_PHASE = {
  problem_hypothesis: 0,
  external_mathematical_result: 0,
  mathematical_claim: 1,
  mathematical_inference: 2,
  verified_counterexample: 2,
  research_goal: 3,
  proof_obligation: 3,
  research_attempt: 4,
  basic_assumption: 0,
  definition_contract: 0,
  theory_from_assumptions: 1,
  numerical_method: 1,
  numerical_result: 2,
  numerical_experiment_design: 3,
  theory_from_numerics: 3,
  superseded: 4,
};

const MAINLINE_ORDER = ["mathematics", "research", "support", "theory", "simulation", "synthesis", "archive"];

const MAINLINE_LABELS = {
  mathematics: "数学证明",
  research: "开放研究",
  theory: "理论主线",
  support: "定义与合同",
  simulation: "数值模拟",
  synthesis: "理论—数值综合",
  archive: "归档",
};

const TYPE_LABELS = {
  problem_hypothesis: "题目假设",
  external_mathematical_result: "文献定理",
  mathematical_claim: "数学命题",
  mathematical_inference: "推理步骤",
  verified_counterexample: "已验证反例",
  research_goal: "研究目标",
  proof_obligation: "证明义务",
  research_attempt: "研究尝试",
  basic_assumption: "基础假设",
  definition_contract: "定义合同",
  theory_from_assumptions: "基础假设演绎",
  numerical_method: "数值方法",
  numerical_result: "数值结果",
  numerical_experiment_design: "数值实验设计",
  theory_from_numerics: "数值结果上的理论",
  superseded: "已归档",
};

const TYPE_MARKERS = {
  problem_hypothesis: "H",
  external_mathematical_result: "E",
  mathematical_claim: "P",
  mathematical_inference: "⇒",
  verified_counterexample: "¬",
  research_goal: "G",
  proof_obligation: "?",
  research_attempt: "R",
  basic_assumption: "A",
  definition_contract: "C",
  theory_from_assumptions: "T1",
  numerical_method: "M",
  numerical_result: "N",
  numerical_experiment_design: "D",
  theory_from_numerics: "T2",
  superseded: "X",
};

const TYPE_VARIABLES = {
  problem_hypothesis: ["--assumption-fill", "--assumption-stroke"],
  external_mathematical_result: ["--theory-fill", "--theory-stroke"],
  mathematical_claim: ["--theory-fill", "--theory-stroke"],
  mathematical_inference: ["--synthesis-fill", "--synthesis-stroke"],
  verified_counterexample: ["--archive-fill", "--archive-stroke"],
  research_goal: ["--design-fill", "--design-stroke"],
  proof_obligation: ["--design-fill", "--design-stroke"],
  research_attempt: ["--method-fill", "--method-stroke"],
  basic_assumption: ["--assumption-fill", "--assumption-stroke"],
  definition_contract: ["--contract-fill", "--contract-stroke"],
  theory_from_assumptions: ["--theory-fill", "--theory-stroke"],
  numerical_method: ["--method-fill", "--method-stroke"],
  numerical_result: ["--result-fill", "--result-stroke"],
  numerical_experiment_design: ["--design-fill", "--design-stroke"],
  theory_from_numerics: ["--synthesis-fill", "--synthesis-stroke"],
  superseded: ["--archive-fill", "--archive-stroke"],
};

const refs = {
  overviewButton: document.getElementById("overview-button"),
  detailButton: document.getElementById("detail-button"),
  fitButton: document.getElementById("fit-button"),
  zoomInButton: document.getElementById("zoom-in-button"),
  zoomOutButton: document.getElementById("zoom-out-button"),
  exportButton: document.getElementById("export-button"),
  fileInput: document.getElementById("file-input"),
  searchInput: document.getElementById("search-input"),
  edgeMode: document.getElementById("edge-mode"),
  mainlineFilters: document.getElementById("mainline-filters"),
  typeFilters: document.getElementById("type-filters"),
  selectAllButton: document.getElementById("select-all-button"),
  clearFiltersButton: document.getElementById("clear-filters-button"),
  projectMeta: document.getElementById("project-meta"),
  graphPane: document.getElementById("graph-pane"),
  graphSvg: document.getElementById("graph-svg"),
  scene: document.getElementById("scene"),
  emptyState: document.getElementById("empty-state"),
  detailPanel: document.getElementById("detail-panel"),
};

const state = {
  model: null,
  mode: "overview",
  selectedId: null,
  moduleFocus: null,
  mainlines: new Set(),
  types: new Set(),
  edgeMode: "context",
  camera: { x: 0, y: 0, k: 1 },
  layout: { width: 100, height: 100 },
  dragging: { active: false, moved: false, startX: 0, startY: 0, originX: 0, originY: 0 },
};

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    if (value !== undefined && value !== null) {
      element.setAttribute(key, String(value));
    }
  }
  return element;
}

function htmlElement(name, attributes = {}) {
  const element = document.createElement(name);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "class") {
      element.className = value;
    } else if (key === "text") {
      element.textContent = value;
    } else {
      element.setAttribute(key, value);
    }
  }
  return element;
}

function cssColor(variable) {
  return getComputedStyle(document.documentElement).getPropertyValue(variable).trim() || "#777";
}

function typeStyle(type) {
  const [fillVariable, strokeVariable] = TYPE_VARIABLES[type] || TYPE_VARIABLES.definition_contract;
  return { fill: cssColor(fillVariable), stroke: cssColor(strokeVariable) };
}

function typeOrder(type) {
  const index = TYPE_ORDER.indexOf(type);
  return index === -1 ? TYPE_ORDER.length : index;
}

function mainlineOrder(mainline) {
  const index = MAINLINE_ORDER.indexOf(mainline);
  return index === -1 ? MAINLINE_ORDER.length : index;
}

function canonicalLabel(value) {
  return String(value || "").replace(/_/g, " ");
}

function nodeDisplayType(node) {
  return node.epistemic_type || "definition_contract";
}

function normalizeEdge(rawEdge) {
  if (Array.isArray(rawEdge) && rawEdge.length === 2) {
    return { source: rawEdge[0], target: rawEdge[1] };
  }
  if (rawEdge && typeof rawEdge === "object" && rawEdge.source && rawEdge.target) {
    return {
      source: rawEdge.source,
      target: rawEdge.target,
      relation: rawEdge.role || rawEdge.relation,
    };
  }
  return null;
}

function buildModel(raw) {
  const issues = [];
  if (!raw || !Array.isArray(raw.nodes)) {
    throw new Error("Blueprint 必须包含 nodes 数组。");
  }

  const seen = new Set();
  const nodes = [];
  for (const rawNode of raw.nodes) {
    if (!rawNode || typeof rawNode !== "object" || !rawNode.id) {
      issues.push("跳过了一个缺少 id 的节点。");
      continue;
    }
    if (seen.has(rawNode.id)) {
      issues.push(`检测到重复节点 ID：${rawNode.id}`);
      continue;
    }
    seen.add(rawNode.id);
    nodes.push({
      ...rawNode,
      title: rawNode.title || rawNode.id,
      mainline: rawNode.mainline || "unclassified",
      epistemic_type: rawNode.epistemic_type || "definition_contract",
      grade: rawNode.grade || "—",
      status: rawNode.status || "unknown",
    });
  }

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = [];
  for (const rawEdge of raw.edges || []) {
    const edge = normalizeEdge(rawEdge);
    if (!edge || !byId.has(edge.source) || !byId.has(edge.target)) {
      issues.push(`跳过了未知端点依赖：${JSON.stringify(rawEdge)}`);
      continue;
    }
    const target = byId.get(edge.target);
    edges.push({
      ...edge,
      id: `${edge.source}→${edge.target}`,
      relation: edge.relation || inferRelation(edge.source, target),
    });
  }

  const incoming = new Map(nodes.map((node) => [node.id, []]));
  const outgoing = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    incoming.get(edge.target).push(edge.source);
    outgoing.get(edge.source).push(edge.target);
  }

  const taxonomy = raw.taxonomy || {};
  const mainlineLabels = taxonomy.mainlines || {};
  const typeLabels = taxonomy.epistemic_types || {};
  const mainlines = uniqueOrdered(
    [...Object.keys(mainlineLabels), ...nodes.map((node) => node.mainline)],
    mainlineOrder,
  );
  const types = uniqueOrdered(
    [...Object.keys(typeLabels), ...nodes.map((node) => node.epistemic_type)],
    typeOrder,
  );

  const displayGroups = new Map();
  for (const group of raw.display?.groups || []) {
    if (group?.id) {
      displayGroups.set(group.id, group);
    }
  }

  const groupMembers = new Map();
  for (const node of nodes) {
    const groupId = node.display?.group || `auto:${node.mainline}:${node.epistemic_type}`;
    if (!groupMembers.has(groupId)) {
      groupMembers.set(groupId, []);
    }
    groupMembers.get(groupId).push(node.id);
  }

  return {
    raw,
    nodes,
    edges,
    byId,
    incoming,
    outgoing,
    mainlines,
    types,
    mainlineLabels,
    typeLabels,
    displayGroups,
    groupMembers,
    issues,
  };
}

function inferRelation(sourceId, target) {
  if ((target.assumptions || []).includes(sourceId)) return "assumption";
  if ((target.theory_inputs || []).includes(sourceId)) return "theory_input";
  if ((target.numerical_inputs || []).includes(sourceId)) return "numerical_input";
  if ((target.method_inputs || []).includes(sourceId)) return "method_input";
  if ((target.premise_inputs || []).includes(sourceId)) return "premise_input";
  if ((target.definition_inputs || []).includes(sourceId)) return "definition_input";
  if ((target.inference_inputs || []).includes(sourceId)) return "inference_input";
  if ((target.refutation_inputs || []).includes(sourceId)) return "refutation_input";
  if ((target.target_inputs || []).includes(sourceId)) return "target_input";
  return "support";
}

function uniqueOrdered(values, orderFunction) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => {
    const delta = orderFunction(a) - orderFunction(b);
    return delta || String(a).localeCompare(String(b), "zh-CN");
  });
}

function mainlineLabel(mainline) {
  return MAINLINE_LABELS[mainline] || canonicalLabel(mainline);
}

function typeLabel(type) {
  return TYPE_LABELS[type] || state.model?.typeLabels?.[type] || canonicalLabel(type);
}

function groupLabel(groupId, members) {
  const configured = state.model.displayGroups.get(groupId);
  if (configured?.label) return configured.label;
  const first = members[0];
  return `${mainlineLabel(first.mainline)} · ${typeLabel(first.epistemic_type)}`;
}

function loadBlueprint(raw, sourceLabel = "已载入") {
  state.model = buildModel(raw);
  state.mode = "overview";
  state.selectedId = null;
  state.moduleFocus = null;
  state.mainlines = new Set(state.model.mainlines);
  state.types = new Set(state.model.types);
  state.edgeMode = "context";
  refs.edgeMode.value = "context";
  refs.searchInput.value = "";
  buildFilterControls();
  updateProjectMeta(sourceLabel);
  render({ fit: true });
}

function updateProjectMeta(sourceLabel = "") {
  if (!state.model) return;
  const project = state.model.raw.project || {};
  const title = project.title || project.id || "未命名 Blueprint";
  const version = project.version ? `v${project.version}` : "";
  refs.projectMeta.textContent = `${title} ${version} · ${state.model.nodes.length} 个节点 / ${state.model.edges.length} 条关系 · ${sourceLabel}`;
}

function buildFilterControls() {
  refs.mainlineFilters.replaceChildren();
  refs.typeFilters.replaceChildren();

  for (const mainline of state.model.mainlines) {
    const filter = createFilterItem("mainline", mainline, mainlineLabel(mainline), state.mainlines);
    filter.title = state.model.mainlineLabels?.[mainline] || mainlineLabel(mainline);
    refs.mainlineFilters.append(filter);
  }
  for (const type of state.model.types) {
    refs.typeFilters.append(createFilterItem("type", type, typeLabel(type), state.types));
  }
}

function createFilterItem(kind, value, label, selected) {
  const wrapper = htmlElement("label", { class: "filter-item" });
  const input = htmlElement("input", { type: "checkbox", value });
  input.checked = selected.has(value);
  input.addEventListener("change", () => {
    const set = kind === "mainline" ? state.mainlines : state.types;
    if (input.checked) set.add(value);
    else set.delete(value);
    state.selectedId = null;
    state.moduleFocus = null;
    render({ fit: true });
  });
  wrapper.append(input, document.createTextNode(label));
  return wrapper;
}

function visibleNodes() {
  if (!state.model) return [];
  const query = refs.searchInput.value.trim().toLocaleLowerCase();
  let candidates = state.model.nodes.filter((node) => {
    if (!state.mainlines.has(node.mainline) || !state.types.has(node.epistemic_type)) return false;
    if (!query) return true;
    const haystack = `${node.id} ${node.title} ${node.statement || ""} ${node.status || ""}`.toLocaleLowerCase();
    return haystack.includes(query);
  });

  if (state.moduleFocus && state.model.groupMembers.has(state.moduleFocus)) {
    const focus = new Set(state.model.groupMembers.get(state.moduleFocus));
    for (const nodeId of [...focus]) {
      for (const parent of state.model.incoming.get(nodeId) || []) focus.add(parent);
      for (const child of state.model.outgoing.get(nodeId) || []) focus.add(child);
    }
    candidates = candidates.filter((node) => focus.has(node.id));
  }
  return candidates;
}

function visibleEdges(nodeIds) {
  const visible = new Set(nodeIds);
  return state.model.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target));
}

function buildOverview(nodes, edges) {
  const groupMap = new Map();
  for (const node of nodes) {
    const groupId = node.display?.group || `auto:${node.mainline}:${node.epistemic_type}`;
    if (!groupMap.has(groupId)) {
      groupMap.set(groupId, {
        id: groupId,
        kind: "group",
        members: [],
        mainline: node.mainline,
        types: new Set(),
      });
    }
    const group = groupMap.get(groupId);
    group.members.push(node);
    group.types.add(node.epistemic_type);
  }

  const groupByNodeId = new Map();
  for (const group of groupMap.values()) {
    for (const node of group.members) groupByNodeId.set(node.id, group.id);
  }

  const aggregateEdges = new Map();
  for (const edge of edges) {
    const source = groupByNodeId.get(edge.source);
    const target = groupByNodeId.get(edge.target);
    if (!source || !target || source === target) continue;
    const id = `${source}→${target}`;
    if (!aggregateEdges.has(id)) {
      aggregateEdges.set(id, { id, source, target, count: 0, relation: "aggregate" });
    }
    aggregateEdges.get(id).count += 1;
  }

  const visualNodes = [...groupMap.values()].map((group) => {
    const memberTypes = [...group.types].sort((a, b) => typeOrder(a) - typeOrder(b));
    const primaryType = memberTypes[0] || "definition_contract";
    const internalEdges = edges.filter((edge) => groupByNodeId.get(edge.source) === group.id && groupByNodeId.get(edge.target) === group.id).length;
    return {
      ...group,
      type: primaryType,
      title: groupLabel(group.id, group.members),
      meta: `${group.members.length} 个节点${internalEdges ? ` · ${internalEdges} 条内部依赖` : ""}`,
      phase: Math.min(...memberTypes.map((type) => TYPE_PHASE[type] ?? 5)),
      order: state.model.displayGroups.get(group.id)?.order ?? 999,
    };
  });
  const layout = layoutOverview(visualNodes);
  return { nodes: visualNodes, edges: [...aggregateEdges.values()], layout };
}

function layoutOverview(nodes) {
  const nodeWidth = 280;
  const nodeHeight = 68;
  const laneMargin = 80;
  const rowSpacing = 92;
  const columnSpacing = 92;
  const byMainline = new Map();
  for (const node of nodes) {
    if (!byMainline.has(node.mainline)) byMainline.set(node.mainline, []);
    byMainline.get(node.mainline).push(node);
  }

  const mainlines = uniqueOrdered([...byMainline.keys()], mainlineOrder);
  const laneBoxes = [];
  let cursorY = 70;
  let maxPhase = 0;
  for (const mainline of mainlines) {
    const laneNodes = byMainline.get(mainline).sort((a, b) => a.phase - b.phase || a.order - b.order || a.title.localeCompare(b.title, "zh-CN"));
    const byPhase = new Map();
    for (const node of laneNodes) {
      if (!byPhase.has(node.phase)) byPhase.set(node.phase, []);
      byPhase.get(node.phase).push(node);
      maxPhase = Math.max(maxPhase, node.phase);
    }
    const maxStack = Math.max(1, ...[...byPhase.values()].map((items) => items.length));
    const laneHeight = 62 + maxStack * rowSpacing + 30;
    laneBoxes.push({ mainline, x: 44, y: cursorY, width: 210 + (maxPhase + 1) * (nodeWidth + columnSpacing), height: laneHeight });
    for (const [phase, phaseNodes] of byPhase) {
      phaseNodes.forEach((node, index) => {
        node.x = 150 + phase * (nodeWidth + columnSpacing);
        node.y = cursorY + 52 + index * rowSpacing;
        node.width = nodeWidth;
        node.height = nodeHeight;
      });
    }
    cursorY += laneHeight + laneMargin;
  }
  return {
    width: 260 + (maxPhase + 1) * (nodeWidth + columnSpacing),
    height: cursorY,
    laneBoxes,
    layerLabels: [],
  };
}

function buildDetail(nodes, edges) {
  const visualNodes = nodes.map((node) => ({
    ...node,
    kind: "node",
    type: nodeDisplayType(node),
  }));
  const layout = layoutDetail(visualNodes, edges);
  return { nodes: visualNodes, edges, layout };
}

function layoutDetail(nodes, edges) {
  const nodeWidth = 242;
  const nodeHeight = 66;
  const verticalGap = 14;
  const layerGap = 108;
  const nodeIds = new Set(nodes.map((node) => node.id));
  const depth = topologicalDepth(nodes, edges);
  const grouped = new Map();
  let maxDepth = 0;
  for (const node of nodes) {
    const layer = depth.get(node.id) ?? 0;
    maxDepth = Math.max(maxDepth, layer);
    const key = `${node.mainline}::${layer}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(node);
  }

  const mainlines = uniqueOrdered(nodes.map((node) => node.mainline), mainlineOrder);
  const laneSizes = new Map();
  for (const mainline of mainlines) {
    let maxCount = 1;
    for (let layer = 0; layer <= maxDepth; layer += 1) {
      maxCount = Math.max(maxCount, (grouped.get(`${mainline}::${layer}`) || []).length);
    }
    laneSizes.set(mainline, 56 + maxCount * (nodeHeight + verticalGap) + 28);
  }

  const laneBoxes = [];
  let cursorY = 64;
  const graphWidth = 220 + (maxDepth + 1) * (nodeWidth + layerGap);
  for (const mainline of mainlines) {
    const laneHeight = laneSizes.get(mainline);
    laneBoxes.push({ mainline, x: 42, y: cursorY, width: graphWidth - 78, height: laneHeight });
    for (let layer = 0; layer <= maxDepth; layer += 1) {
      const layerNodes = (grouped.get(`${mainline}::${layer}`) || []).sort((a, b) => typeOrder(a.epistemic_type) - typeOrder(b.epistemic_type) || a.title.localeCompare(b.title, "zh-CN"));
      layerNodes.forEach((node, index) => {
        node.x = 140 + layer * (nodeWidth + layerGap);
        node.y = cursorY + 48 + index * (nodeHeight + verticalGap);
        node.width = nodeWidth;
        node.height = nodeHeight;
      });
    }
    cursorY += laneHeight + 46;
  }

  const layerLabels = [];
  for (let layer = 0; layer <= maxDepth; layer += 1) {
    layerLabels.push({ x: 140 + layer * (nodeWidth + layerGap), y: 34, label: `依赖层 ${layer}` });
  }
  return { width: graphWidth, height: cursorY, laneBoxes, layerLabels, nodeIds };
}

function topologicalDepth(nodes, edges) {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const incomingCount = new Map([...nodeIds].map((id) => [id, 0]));
  const outgoing = new Map([...nodeIds].map((id) => [id, []]));
  const depth = new Map([...nodeIds].map((id) => [id, 0]));
  for (const edge of edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) continue;
    incomingCount.set(edge.target, incomingCount.get(edge.target) + 1);
    outgoing.get(edge.source).push(edge.target);
  }
  const queue = [...nodeIds].filter((id) => incomingCount.get(id) === 0).sort();
  let visited = 0;
  while (queue.length) {
    const source = queue.shift();
    visited += 1;
    for (const target of outgoing.get(source)) {
      depth.set(target, Math.max(depth.get(target), depth.get(source) + 1));
      incomingCount.set(target, incomingCount.get(target) - 1);
      if (incomingCount.get(target) === 0) queue.push(target);
    }
  }
  if (visited !== nodeIds.size) {
    for (const id of nodeIds) {
      if (incomingCount.get(id) > 0) depth.set(id, Math.max(depth.get(id), 1));
    }
  }
  return depth;
}

function edgePath(source, target) {
  const sx = source.x + source.width;
  const sy = source.y + source.height / 2;
  const tx = target.x;
  const ty = target.y + target.height / 2;
  const distance = Math.max(55, Math.abs(tx - sx) * 0.46);
  if (tx >= sx) {
    return `M ${sx} ${sy} C ${sx + distance} ${sy}, ${tx - distance} ${ty}, ${tx} ${ty}`;
  }
  const bend = Math.max(source.x + source.width, target.x + target.width) + 44;
  return `M ${sx} ${sy} C ${bend} ${sy}, ${bend} ${ty}, ${tx} ${ty}`;
}

function edgeStyle(relation) {
  const muted = cssColor("--muted");
  if (relation === "assumption") return { color: cssColor("--assumption-stroke"), dash: "5 4" };
  if (relation === "theory_input") return { color: cssColor("--theory-stroke"), dash: "" };
  if (relation === "numerical_input") return { color: cssColor("--result-stroke"), dash: "" };
  if (relation === "method_input") return { color: cssColor("--method-stroke"), dash: "3 3" };
  return { color: muted, dash: "" };
}

function getSelectionContext(graph) {
  if (!state.selectedId) return { relatedNodes: new Set(), relatedEdges: new Set() };
  if (state.mode === "overview") {
    const relatedEdges = new Set(graph.edges.filter((edge) => edge.source === state.selectedId || edge.target === state.selectedId).map((edge) => edge.id));
    const relatedNodes = new Set([state.selectedId]);
    for (const edge of graph.edges) {
      if (relatedEdges.has(edge.id)) {
        relatedNodes.add(edge.source);
        relatedNodes.add(edge.target);
      }
    }
    return { relatedNodes, relatedEdges };
  }
  const relatedNodes = new Set([state.selectedId]);
  const relatedEdges = new Set();
  for (const edge of graph.edges) {
    if (edge.source === state.selectedId || edge.target === state.selectedId) {
      relatedNodes.add(edge.source);
      relatedNodes.add(edge.target);
      relatedEdges.add(edge.id);
    }
  }
  return { relatedNodes, relatedEdges };
}

function drawScene(graph) {
  refs.scene.replaceChildren();
  const positions = new Map(graph.nodes.map((node) => [node.id, node]));
  const selection = getSelectionContext(graph);
  const groupLayer = svgElement("g", { class: "group-layer" });
  const edgeLayer = svgElement("g", { class: "edge-layer" });
  const nodeLayer = svgElement("g", { class: "node-layer" });

  for (const lane of graph.layout.laneBoxes || []) {
    const laneBox = svgElement("rect", {
      x: lane.x,
      y: lane.y,
      width: lane.width,
      height: lane.height,
      rx: 16,
      class: "lane-box",
    });
    const laneLabel = svgElement("text", { x: lane.x + 14, y: lane.y + 24, class: "lane-label" });
    laneLabel.textContent = mainlineLabel(lane.mainline);
    groupLayer.append(laneBox, laneLabel);
  }
  for (const layer of graph.layout.layerLabels || []) {
    const label = svgElement("text", { x: layer.x, y: layer.y, class: "layer-label" });
    label.textContent = layer.label;
    groupLayer.append(label);
  }

  for (const edge of graph.edges) {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) continue;
    const style = edgeStyle(edge.relation);
    const path = svgElement("path", {
      d: edgePath(source, target),
      class: "edge",
      "marker-end": "url(#arrow-head)",
      stroke: style.color,
      color: style.color,
      "stroke-dasharray": style.dash,
    });
    if (selection.relatedEdges.has(edge.id)) path.classList.add("is-related");
    else if (state.selectedId && state.edgeMode !== "all") path.classList.add("is-dimmed");
    else if (!state.selectedId && state.edgeMode === "focused") path.style.opacity = "0";
    edgeLayer.append(path);

    if (state.mode === "overview" && edge.count > 1) {
      const label = svgElement("text", {
        x: (source.x + source.width + target.x) / 2,
        y: (source.y + source.height / 2 + target.y + target.height / 2) / 2 - 5,
        class: "edge-label",
        "text-anchor": "middle",
      });
      label.textContent = String(edge.count);
      edgeLayer.append(label);
    }
  }

  for (const node of graph.nodes) {
    nodeLayer.append(drawNode(node, selection));
  }
  refs.scene.append(groupLayer, edgeLayer, nodeLayer);
}

function drawNode(node, selection) {
  const group = svgElement("g", {
    class: "graph-node",
    transform: `translate(${node.x} ${node.y})`,
    role: "button",
    tabindex: "0",
    "data-node-id": node.id,
    "data-node-kind": node.kind,
    "aria-label": `${node.title}，${node.meta || node.id}`,
  });
  const style = typeStyle(node.type);
  const dashed = node.type === "numerical_experiment_design" || node.type === "superseded";
  const box = svgElement("rect", {
    x: 0,
    y: 0,
    width: node.width,
    height: node.height,
    rx: 10,
    class: "node-box",
    fill: style.fill,
    stroke: style.stroke,
    "stroke-dasharray": dashed ? "6 4" : "",
  });
  group.append(box);

  const marker = TYPE_MARKERS[node.type] || "·";
  const nodeLabel = node.kind === "group" ? node.title : (node.display?.short_label || node.title);
  const title = node.kind === "group" ? nodeLabel : `[${marker}] ${nodeLabel}`;
  const maxChars = node.kind === "group" ? 22 : 24;
  const titleLines = wrapLabel(title, maxChars, 2);
  titleLines.forEach((line, index) => {
    const label = svgElement("text", { x: 11, y: 21 + index * 16, class: "node-title" });
    label.textContent = line;
    group.append(label);
  });
  const metaText = node.kind === "group" ? node.meta : `${node.id} · ${node.grade}`;
  const meta = svgElement("text", { x: 11, y: node.height - 10, class: "node-meta" });
  meta.textContent = truncate(metaText, Math.max(22, Math.floor(node.width / 7)));
  group.append(meta);

  if (state.selectedId === node.id) group.classList.add("is-selected");
  if (selection.relatedNodes.has(node.id) && state.selectedId !== node.id) group.classList.add("is-related");
  if (state.selectedId && !selection.relatedNodes.has(node.id)) group.classList.add("is-dimmed");

  return group;
}

function wrapLabel(value, maxChars, maxLines) {
  if (value.length <= maxChars) return [value];
  const lines = [];
  let cursor = 0;
  while (cursor < value.length && lines.length < maxLines) {
    lines.push(value.slice(cursor, cursor + maxChars));
    cursor += maxChars;
  }
  if (cursor < value.length) {
    lines[maxLines - 1] = `${lines[maxLines - 1].slice(0, -1)}…`;
  }
  return lines;
}

function truncate(value, maxChars) {
  return value.length > maxChars ? `${value.slice(0, maxChars - 1)}…` : value;
}

function render(options = {}) {
  if (!state.model) return;
  const nodes = visibleNodes();
  const nodeIds = nodes.map((node) => node.id);
  const edges = visibleEdges(nodeIds);
  if (state.selectedId && !nodeIds.includes(state.selectedId)) {
    state.selectedId = null;
  }

  const graph = state.mode === "overview" ? buildOverview(nodes, edges) : buildDetail(nodes, edges);
  state.layout = graph.layout;
  refs.emptyState.hidden = graph.nodes.length > 0;
  refs.emptyState.textContent = graph.nodes.length ? "" : "当前筛选没有匹配节点。请调整筛选条件或清除搜索。";
  drawScene(graph);
  renderDetails();
  setModeButtons();
  if (options.fit) requestAnimationFrame(fitGraph);
}

function selectNode(nodeId) {
  state.selectedId = state.selectedId === nodeId ? null : nodeId;
  render({ fit: false });
}

function focusGroup(groupId) {
  state.moduleFocus = groupId;
  state.selectedId = null;
  state.mode = "detail";
  render({ fit: true });
}

function renderDetails() {
  refs.detailPanel.replaceChildren();
  if (!state.model) return;
  if (!state.selectedId) {
    if (state.moduleFocus) {
      const members = state.model.groupMembers.get(state.moduleFocus) || [];
      const title = groupLabel(state.moduleFocus, members.map((id) => state.model.byId.get(id)).filter(Boolean));
      refs.detailPanel.append(
        htmlElement("p", { class: "detail-title", text: title }),
        htmlElement("p", { class: "detail-meta", text: `已展开模块：${members.length} 个核心节点，并显示其直接上下游。` }),
      );
      const button = htmlElement("button", { type: "button", text: "返回完整视图" });
      button.addEventListener("click", () => {
        state.moduleFocus = null;
        render({ fit: true });
      });
      refs.detailPanel.append(button);
      return;
    }
    refs.detailPanel.className = "detail-empty";
    refs.detailPanel.textContent = "选择一个节点以查看其假设、输入、直接上下游和证据状态。";
    return;
  }

  refs.detailPanel.className = "";
  const node = state.model.byId.get(state.selectedId);
  if (!node) return;
  refs.detailPanel.append(
    htmlElement("h3", { class: "detail-title", text: node.title }),
    htmlElement("p", { class: "detail-id", text: node.id }),
  );

  const tags = htmlElement("div", { class: "detail-tags" });
  tags.append(
    htmlElement("span", { class: "badge", text: mainlineLabel(node.mainline) }),
    htmlElement("span", { class: "badge", text: typeLabel(node.epistemic_type) }),
    htmlElement("span", { class: "badge", text: `等级 ${node.grade}` }),
    htmlElement("span", { class: "badge", text: node.status }),
  );
  refs.detailPanel.append(tags);
  if (node.statement) refs.detailPanel.append(htmlElement("p", { class: "detail-statement", text: node.statement }));

  appendNodeList("基本假设", node.assumptions || []);
  appendNodeList("理论输入", node.theory_inputs || []);
  appendNodeList("数值输入", node.numerical_inputs || []);
  appendNodeList("方法输入", node.method_inputs || []);
  appendNodeList("证明前提", node.premise_inputs || []);
  appendNodeList("定义输入", node.definition_inputs || []);
  appendNodeList("结论推理", node.inference_inputs || []);
  appendNodeList("反驳输入", node.refutation_inputs || []);
  appendNodeList("研究目标", node.target_inputs || []);
  appendNodeList("推理结论", node.conclusion ? [node.conclusion] : []);
  appendNodeList("直接上游", state.model.incoming.get(node.id) || []);
  appendNodeList("直接下游", state.model.outgoing.get(node.id) || []);

  if (node.precise_gap) {
    refs.detailPanel.append(
      htmlElement("h4", { text: "精确缺口" }),
      htmlElement("p", { class: "detail-statement", text: node.precise_gap }),
    );
  }

  const boundArtifact = node.proof_package || node.refutation_package || node.certificate;
  if (boundArtifact?.path) {
    refs.detailPanel.append(
      htmlElement("h4", { text: "数学证据绑定" }),
      htmlElement("p", {
        class: "detail-statement",
        text: `${boundArtifact.path} · ${boundArtifact.sha256 || "未记录哈希"}`,
      }),
    );
  }

  if (node.artifacts?.length) {
    const heading = htmlElement("h4", { text: "证据产物" });
    const list = htmlElement("ul", { class: "detail-list" });
    for (const artifact of node.artifacts) {
      const item = document.createElement("li");
      const code = document.createElement("code");
      code.textContent = artifact;
      item.append(code);
      list.append(item);
    }
    refs.detailPanel.append(heading, list);
  }
}

function appendNodeList(title, ids) {
  if (!ids.length) return;
  const heading = htmlElement("h4", { text: title });
  const list = htmlElement("ul", { class: "detail-list" });
  for (const id of ids) {
    const related = state.model.byId.get(id);
    const item = document.createElement("li");
    if (!related) {
      item.textContent = id;
    } else {
      const button = htmlElement("button", { type: "button", text: `${related.title} (${id})` });
      button.addEventListener("click", () => selectNode(id));
      item.append(button);
    }
    list.append(item);
  }
  refs.detailPanel.append(heading, list);
}

function setModeButtons() {
  const overview = state.mode === "overview";
  refs.overviewButton.setAttribute("aria-pressed", String(overview));
  refs.detailButton.setAttribute("aria-pressed", String(!overview));
}

function applyCamera() {
  refs.scene.setAttribute("transform", `translate(${state.camera.x} ${state.camera.y}) scale(${state.camera.k})`);
}

function fitGraph() {
  const rect = refs.graphPane.getBoundingClientRect();
  const padding = 42;
  const k = Math.max(0.08, Math.min((rect.width - padding) / state.layout.width, (rect.height - padding) / state.layout.height));
  state.camera.k = k;
  state.camera.x = (rect.width - state.layout.width * k) / 2;
  state.camera.y = (rect.height - state.layout.height * k) / 2;
  applyCamera();
}

function zoomAt(clientX, clientY, factor) {
  const rect = refs.graphSvg.getBoundingClientRect();
  const pointX = clientX - rect.left;
  const pointY = clientY - rect.top;
  const oldK = state.camera.k;
  const newK = Math.max(0.08, Math.min(4, oldK * factor));
  state.camera.x = pointX - ((pointX - state.camera.x) * newK) / oldK;
  state.camera.y = pointY - ((pointY - state.camera.y) * newK) / oldK;
  state.camera.k = newK;
  applyCamera();
}

function clearSelection() {
  if (state.selectedId) {
    state.selectedId = null;
    render({ fit: false });
  }
}

function exportSvg() {
  const clone = refs.graphSvg.cloneNode(true);
  clone.setAttribute("xmlns", SVG_NS);
  clone.setAttribute("width", String(Math.ceil(state.layout.width)));
  clone.setAttribute("height", String(Math.ceil(state.layout.height)));
  clone.setAttribute("viewBox", `0 0 ${Math.ceil(state.layout.width)} ${Math.ceil(state.layout.height)}`);
  const exportedScene = clone.querySelector("#scene");
  if (exportedScene) exportedScene.setAttribute("transform", "");
  const style = svgElement("style");
  style.textContent = ".lane-box{fill:none;stroke:#9aa5b1;stroke-dasharray:4 4}.lane-label,.layer-label{fill:#53606d;font:600 13px sans-serif}.node-title{fill:#18202a;font:600 13px sans-serif}.node-meta{fill:#5f6b77;font:10px sans-serif}.edge{fill:none;stroke-width:1.2;opacity:.42}.edge.is-related{stroke-width:2.2;opacity:.92}.edge-label{fill:#53606d;font:12px sans-serif}";
  clone.insertBefore(style, clone.firstChild);
  const blob = new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.model.raw.project?.id || "blueprint"}-view.svg`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function bindEvents() {
  refs.overviewButton.addEventListener("click", () => {
    state.mode = "overview";
    state.selectedId = null;
    state.moduleFocus = null;
    render({ fit: true });
  });
  refs.detailButton.addEventListener("click", () => {
    state.mode = "detail";
    state.selectedId = null;
    render({ fit: true });
  });
  refs.fitButton.addEventListener("click", fitGraph);
  refs.zoomInButton.addEventListener("click", () => {
    const rect = refs.graphSvg.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.24);
  });
  refs.zoomOutButton.addEventListener("click", () => {
    const rect = refs.graphSvg.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1 / 1.24);
  });
  refs.exportButton.addEventListener("click", exportSvg);
  refs.searchInput.addEventListener("input", () => {
    state.selectedId = null;
    state.moduleFocus = null;
    render({ fit: true });
  });
  refs.edgeMode.addEventListener("change", () => {
    state.edgeMode = refs.edgeMode.value;
    render({ fit: false });
  });
  refs.selectAllButton.addEventListener("click", () => {
    state.mainlines = new Set(state.model.mainlines);
    state.types = new Set(state.model.types);
    buildFilterControls();
    state.moduleFocus = null;
    render({ fit: true });
  });
  refs.clearFiltersButton.addEventListener("click", () => {
    state.mainlines = new Set(state.model.mainlines);
    state.types = new Set(state.model.types);
    refs.searchInput.value = "";
    state.moduleFocus = null;
    state.selectedId = null;
    buildFilterControls();
    render({ fit: true });
  });
  refs.fileInput.addEventListener("change", async () => {
    const [file] = refs.fileInput.files;
    if (!file) return;
    try {
      loadBlueprint(JSON.parse(await file.text()), `已打开：${file.name}`);
    } catch (error) {
      showError(`无法读取 ${file.name}：${error.message}`);
    }
  });

  refs.graphSvg.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomAt(event.clientX, event.clientY, event.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });
  refs.graphSvg.addEventListener("pointerdown", (event) => {
    if (event.target.closest?.(".graph-node")) return;
    state.dragging = {
      active: true,
      moved: false,
      startX: event.clientX,
      startY: event.clientY,
      originX: state.camera.x,
      originY: state.camera.y,
    };
    refs.graphSvg.classList.add("panning");
    refs.graphSvg.setPointerCapture(event.pointerId);
  });
  refs.graphSvg.addEventListener("pointermove", (event) => {
    if (!state.dragging.active) return;
    const dx = event.clientX - state.dragging.startX;
    const dy = event.clientY - state.dragging.startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) state.dragging.moved = true;
    state.camera.x = state.dragging.originX + dx;
    state.camera.y = state.dragging.originY + dy;
    applyCamera();
  });
  refs.graphSvg.addEventListener("pointerup", (event) => {
    if (state.dragging.active) {
      refs.graphSvg.releasePointerCapture?.(event.pointerId);
      refs.graphSvg.classList.remove("panning");
      state.dragging.active = false;
    }
  });
  refs.graphSvg.addEventListener("click", (event) => {
    const nodeElement = event.target.closest?.(".graph-node");
    if (nodeElement) {
      const nodeId = nodeElement.dataset.nodeId;
      if (nodeElement.dataset.nodeKind === "group") focusGroup(nodeId);
      else selectNode(nodeId);
      return;
    }
    if (!state.dragging.moved) clearSelection();
    state.dragging.moved = false;
  });
  refs.graphSvg.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const nodeElement = event.target.closest?.(".graph-node");
    if (!nodeElement) return;
    event.preventDefault();
    const nodeId = nodeElement.dataset.nodeId;
    if (nodeElement.dataset.nodeKind === "group") focusGroup(nodeId);
    else selectNode(nodeId);
  });
  window.addEventListener("resize", () => fitGraph());
}

function showError(message) {
  refs.emptyState.hidden = false;
  refs.emptyState.textContent = message;
  refs.projectMeta.textContent = message;
  refs.detailPanel.textContent = message;
}

async function start() {
  bindEvents();
  try {
    const response = await fetch("../blueprint.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    loadBlueprint(await response.json(), "默认文件");
  } catch (error) {
    showError(`默认 Blueprint 无法读取（${error.message}）。请用“打开 Blueprint JSON”选择文件，或通过本目录提供的本地启动脚本打开。`);
  }
}

window.BlueprintViewer = {
  load: (data) => loadBlueprint(data, "外部载入"),
  fit: fitGraph,
  exportSvg,
};

start();
