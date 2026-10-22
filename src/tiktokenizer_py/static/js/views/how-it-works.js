import { visible } from "../lib/format.js";

// Stage 1 of "How it works": one button per chunk of the split pattern.
export class ChunkList {
  constructor(container, onSelect) {
    this.container = container;
    this.buttons = [];
    this.selected = null;
    container.addEventListener("click", (e) => {
      const target = e.target.closest("[data-i]");
      if (target) onSelect(Number(target.dataset.i));
    });
  }

  render(chunks) {
    const frag = document.createDocumentFragment();
    this.buttons = chunks.map((chunk, i) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = chunk.special ? "chunk special" : "chunk";
      button.dataset.i = i;
      const count = chunk.tokens.length;
      button.title = `${count} ${count === 1 ? "token" : "tokens"}`;
      const text = document.createElement("span");
      text.textContent = visible(chunk.text);
      const badge = document.createElement("span");
      badge.className = "chunk-count";
      badge.textContent = count;
      button.append(text, badge);
      frag.append(button);
      return button;
    });
    this.container.replaceChildren(frag);
    this.selected = null;
  }

  setSelected(i) {
    this.buttons[this.selected]?.classList.remove("selected");
    this.buttons[this.selected]?.setAttribute("aria-pressed", "false");
    this.selected = i;
    this.buttons[i]?.classList.add("selected");
    this.buttons[i]?.setAttribute("aria-pressed", "true");
  }
}

// Stage 2 and 3 of "How it works": one row per merge, then the final pieces with their ids.
export function renderMerges(container, steps, tokens) {
  const frag = document.createDocumentFragment();
  steps.forEach((step, n) => {
    const row = document.createElement("li");
    row.className = "merge-row";
    const label = document.createElement("span");
    label.className = "merge-label";
    label.textContent = n === 0 ? `${step.pieces.length} bytes` : `merge ${n}`;
    row.append(label);
    step.pieces.forEach((piece, i) => {
      const box = document.createElement("span");
      box.className = i === step.merged ? "piece merged" : "piece";
      box.textContent = visible(piece.text);
      box.title = piece.bytes;
      row.append(box);
    });
    frag.append(row);
  });
  const last = steps.at(-1);
  if (last && tokens.length === last.pieces.length) {
    const row = document.createElement("li");
    row.className = "merge-row result";
    const label = document.createElement("span");
    label.className = "merge-label";
    label.textContent = "ids";
    row.append(label);
    last.pieces.forEach((piece, i) => {
      const box = document.createElement("span");
      box.className = "piece final";
      const text = document.createElement("span");
      text.textContent = visible(piece.text);
      const id = document.createElement("span");
      id.className = "piece-id";
      id.textContent = tokens[i];
      box.append(text, id);
      row.append(box);
    });
    frag.append(row);
  }
  container.replaceChildren(frag);
}
