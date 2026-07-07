(function () {
  const FOLDER_COLORS = {
    inbox: "#8b8b8b",
    projects: "#5b9bd5",
    areas: "#70c17c",
    resources: "#e5c07b",
    archives: "#5c5c5c",
  };
  const DEFAULT_COLOR = "#9c8cff";

  const REPEL = 2200;
  const LINK_DIST = 90;
  const LINK_STRENGTH = 0.02;
  const CENTER_STRENGTH = 0.003;
  const DAMPING = 0.85;
  const CLICK_THRESHOLD_SQ = 16; // px^2 of movement before a mousedown counts as a drag, not a click

  const canvas = document.getElementById("graph-canvas");
  const ctx = canvas.getContext("2d");
  const wrap = document.getElementById("graph-wrap");
  const emptyMsg = document.getElementById("graph-empty");

  let nodes = [];
  let links = [];
  let neighborIds = {}; // node id -> Set of itself + every directly linked node id, for hover highlighting
  let hoverNode = null;
  const view = { x: 0, y: 0, scale: 1 };
  let dragNode = null;
  let panStart = null;
  let mouseDownPos = null;
  let draggedFar = false;

  function resize() {
    canvas.width = wrap.clientWidth;
    canvas.height = wrap.clientHeight;
  }
  window.addEventListener("resize", resize);

  function toWorld(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (clientX - rect.left - view.x) / view.scale,
      y: (clientY - rect.top - view.y) / view.scale,
    };
  }

  function nodeAt(clientX, clientY) {
    const { x, y } = toWorld(clientX, clientY);
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      const dx = n.x - x;
      const dy = n.y - y;
      if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
    }
    return null;
  }

  // Repel every node from every other (O(n^2) - fine for a personal vault's
  // note count, not built to scale to tens of thousands of nodes), pull
  // linked nodes toward a target distance, and weakly pull everything
  // toward the canvas center so the graph doesn't drift off-screen.
  function tick() {
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      if (a === dragNode) continue;
      let fx = 0;
      let fy = 0;

      for (let j = 0; j < nodes.length; j++) {
        if (i === j) continue;
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distSq = Math.max(dx * dx + dy * dy, 1);
        const dist = Math.sqrt(distSq);
        const force = REPEL / distSq;
        fx += (dx / dist) * force;
        fy += (dy / dist) * force;
      }

      fx += (canvas.width / 2 / view.scale - a.x) * CENTER_STRENGTH;
      fy += (canvas.height / 2 / view.scale - a.y) * CENTER_STRENGTH;

      a.vx = (a.vx + fx) * DAMPING;
      a.vy = (a.vy + fy) * DAMPING;
    }

    for (const l of links) {
      const a = l.sourceNode;
      const b = l.targetNode;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const diff = (dist - LINK_DIST) * LINK_STRENGTH;
      const fx = (dx / dist) * diff;
      const fy = (dy / dist) * diff;
      if (a !== dragNode) {
        a.vx += fx;
        a.vy += fy;
      }
      if (b !== dragNode) {
        b.vx -= fx;
        b.vy -= fy;
      }
    }

    for (const n of nodes) {
      if (n === dragNode) continue;
      n.x += n.vx;
      n.y += n.vy;
    }
  }

  function draw() {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#1e1e1e";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.scale, view.scale);

    // Hovering a node highlights it and its direct connections by fading
    // everything else, so a dense graph reads as "here's this note's
    // neighborhood" instead of a hairball.
    const highlighted = hoverNode ? neighborIds[hoverNode.id] : null;

    ctx.lineWidth = 1 / view.scale;
    for (const l of links) {
      const connected = !highlighted || (highlighted.has(l.sourceNode.id) && highlighted.has(l.targetNode.id));
      ctx.strokeStyle = connected ? "rgba(220, 221, 222, 0.15)" : "rgba(220, 221, 222, 0.04)";
      ctx.beginPath();
      ctx.moveTo(l.sourceNode.x, l.sourceNode.y);
      ctx.lineTo(l.targetNode.x, l.targetNode.y);
      ctx.stroke();
    }

    for (const n of nodes) {
      const dimmed = highlighted && !highlighted.has(n.id);
      ctx.globalAlpha = dimmed ? 0.25 : 1;
      ctx.beginPath();
      ctx.fillStyle = FOLDER_COLORS[n.group] || DEFAULT_COLOR;
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();

      // Below the normal zoom-to-show-labels threshold, still show labels
      // for the highlighted neighborhood - that's the point of hovering.
      if (!dimmed && (view.scale > 0.6 || highlighted)) {
        ctx.fillStyle = "#dcddde";
        ctx.font = `${12 / view.scale}px sans-serif`;
        ctx.fillText(n.title, n.x + n.r + 4, n.y + 4);
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  function loop() {
    tick();
    draw();
    requestAnimationFrame(loop);
  }

  canvas.addEventListener("mousedown", (e) => {
    mouseDownPos = { x: e.clientX, y: e.clientY };
    draggedFar = false;
    const n = nodeAt(e.clientX, e.clientY);
    if (n) {
      dragNode = n;
      canvas.style.cursor = "grabbing";
    } else {
      panStart = { x: e.clientX - view.x, y: e.clientY - view.y };
    }
  });

  window.addEventListener("mousemove", (e) => {
    if (mouseDownPos) {
      const dx = e.clientX - mouseDownPos.x;
      const dy = e.clientY - mouseDownPos.y;
      if (dx * dx + dy * dy > CLICK_THRESHOLD_SQ) draggedFar = true;
    }
    if (dragNode) {
      const { x, y } = toWorld(e.clientX, e.clientY);
      dragNode.x = x;
      dragNode.y = y;
      dragNode.vx = 0;
      dragNode.vy = 0;
    } else if (panStart) {
      view.x = e.clientX - panStart.x;
      view.y = e.clientY - panStart.y;
    } else {
      hoverNode = nodeAt(e.clientX, e.clientY);
      canvas.style.cursor = hoverNode ? "pointer" : "grab";
    }
  });

  window.addEventListener("mouseup", (e) => {
    if (dragNode && !draggedFar) {
      window.location.href = `/notes/${dragNode.id}`;
    }
    dragNode = null;
    panStart = null;
    mouseDownPos = null;
    canvas.style.cursor = "grab";
  });

  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const worldX = (mx - view.x) / view.scale;
      const worldY = (my - view.y) / view.scale;

      view.scale = Math.max(0.15, Math.min(4, view.scale * zoomFactor));
      view.x = mx - worldX * view.scale;
      view.y = my - worldY * view.scale;
    },
    { passive: false }
  );

  resize();

  fetch("/graph-data")
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        emptyMsg.textContent = data.error;
        emptyMsg.style.display = "block";
        return;
      }
      if (!data.nodes || !data.nodes.length) {
        emptyMsg.textContent = "No notes to show yet.";
        emptyMsg.style.display = "block";
        return;
      }

      const byId = {};
      nodes = data.nodes.map((n) => {
        const node = {
          id: n.id,
          title: n.title,
          group: n.group,
          x: canvas.width / 2 + (Math.random() - 0.5) * 200,
          y: canvas.height / 2 + (Math.random() - 0.5) * 200,
          vx: 0,
          vy: 0,
          r: 6,
        };
        byId[n.id] = node;
        return node;
      });

      links = (data.links || [])
        .map((l) => ({ sourceNode: byId[l.source], targetNode: byId[l.target] }))
        .filter((l) => l.sourceNode && l.targetNode);

      // Bigger node for a more-connected note, like Obsidian's degree-scaled nodes.
      for (const l of links) {
        l.sourceNode.r += 0.6;
        l.targetNode.r += 0.6;
      }

      neighborIds = {};
      for (const n of nodes) neighborIds[n.id] = new Set([n.id]);
      for (const l of links) {
        neighborIds[l.sourceNode.id].add(l.targetNode.id);
        neighborIds[l.targetNode.id].add(l.sourceNode.id);
      }

      loop();
    })
    .catch(() => {
      emptyMsg.textContent = "Couldn't load graph data.";
      emptyMsg.style.display = "block";
    });
})();
