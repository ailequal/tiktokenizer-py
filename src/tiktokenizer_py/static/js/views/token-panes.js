import { encodeWhitespace } from "../lib/format.js";

const PALETTE_SIZE = 19;
// Above this many segments, hovering does not dim the other segments: restyling tens of
// thousands of spans on every mouse move makes the page stutter.
const DIM_LIMIT = 4000;
// Panes render at most this many segments until "Show all" is pressed: every segment is a
// span in two panes, and very large results take seconds for the browser to lay out and paint.
const RENDER_LIMIT = 5000;

// Renders segments and ids into two <pre> panes, links them on hover and selects on click.
// The segment pane is one Tab stop: arrow keys move between segments (focus highlights their
// ids like hovering does) and Enter or Space selects one.
export class TokenPanes {
  constructor(segPane, idPane, onSelect) {
    this.segPane = segPane;
    this.idPane = idPane;
    this.onSelect = onSelect;
    this.segments = [];
    this.segEls = [];
    this.idEls = [];
    this.hot = null;
    this.selected = null;
    this.showWhitespace = false;
    this.focusIndex = 0;
    segPane.addEventListener("keydown", (e) => this.onKey(e));
    segPane.addEventListener("focusin", (e) => {
      const target = e.target.closest("[data-i]");
      if (target) this.setHot(Number(target.dataset.i));
    });
    segPane.addEventListener("focusout", (e) => {
      if (!segPane.contains(e.relatedTarget)) this.setHot(null);
    });
    for (const pane of [segPane, idPane]) {
      pane.addEventListener("mouseover", (e) => this.onOver(e));
      pane.addEventListener("mouseleave", () => this.setHot(null));
      pane.addEventListener("click", (e) => {
        const target = e.target.closest("[data-i]");
        if (target) this.onSelect(Number(target.dataset.i));
      });
    }
  }

  render(allSegments, limit = RENDER_LIMIT) {
    const segments = allSegments.length > limit ? allSegments.slice(0, limit) : allSegments;
    this.hot = null;
    this.selected = null;
    this.segments = segments;
    this.segEls = new Array(segments.length);
    this.idEls = new Array(segments.length);
    const segFrag = document.createDocumentFragment();
    const idFrag = document.createDocumentFragment();
    let first = true;
    segments.forEach((seg, i) => {
      const colour = `c${i % PALETTE_SIZE}`;
      const span = document.createElement("span");
      span.className = seg.special ? `seg ${colour} special` : `seg ${colour}`;
      span.dataset.i = i;
      span.tabIndex = i === 0 ? 0 : -1;
      span.setAttribute("role", "button");
      span.textContent = this.showWhitespace ? encodeWhitespace(seg.text) : seg.text;
      segFrag.append(span);
      this.segEls[i] = span;

      const ids = [];
      for (const token of seg.tokens) {
        if (!first) idFrag.append(", ");
        first = false;
        const id = document.createElement("span");
        id.className = seg.special ? `id ${colour} special` : `id ${colour}`;
        id.dataset.i = i;
        id.textContent = token.id;
        idFrag.append(id);
        ids.push(id);
      }
      this.idEls[i] = ids;
    });
    this.focusIndex = 0;
    this.segPane.replaceChildren(segFrag);
    this.idPane.replaceChildren(idFrag);
    this.segPane.classList.remove("hovering");
    return segments.length;
  }

  setWhitespace(on) {
    this.showWhitespace = on;
    this.segEls.forEach((el, i) => {
      el.textContent = on ? encodeWhitespace(this.segments[i].text) : this.segments[i].text;
    });
  }

  setSelected(i) {
    if (this.selected !== null && this.segEls[this.selected]) {
      this.segEls[this.selected].classList.remove("selected");
      this.idEls[this.selected].forEach((el) => el.classList.remove("selected"));
    }
    this.selected = i;
    if (i === null || !this.segEls[i]) return;
    this.segEls[i].classList.add("selected");
    this.idEls[i].forEach((el) => el.classList.add("selected"));
  }

  onKey(event) {
    const i = Number(event.target.closest("[data-i]")?.dataset.i);
    if (Number.isNaN(i)) return;
    const last = this.segEls.length - 1;
    const next = {
      ArrowRight: Math.min(i + 1, last),
      ArrowDown: Math.min(i + 1, last),
      ArrowLeft: Math.max(i - 1, 0),
      ArrowUp: Math.max(i - 1, 0),
      Home: 0,
      End: last,
    }[event.key];
    if (next !== undefined) {
      event.preventDefault();
      this.moveFocus(next);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this.onSelect(i);
    }
  }

  // Roving focus: only the focused segment is in the Tab order.
  moveFocus(i) {
    const prev = this.segEls[this.focusIndex];
    if (prev) prev.tabIndex = -1;
    this.focusIndex = i;
    const el = this.segEls[i];
    el.tabIndex = 0;
    el.focus();
  }

  onOver(event) {
    const target = event.target.closest("[data-i]");
    if (target) this.setHot(Number(target.dataset.i));
  }

  setHot(i) {
    if (i === this.hot) return;
    if (this.hot !== null && this.segEls[this.hot]) {
      const prev = this.segEls[this.hot];
      prev.classList.remove("hot");
      if (!this.showWhitespace) prev.textContent = this.segments[this.hot].text;
      this.idEls[this.hot].forEach((el) => el.classList.remove("hot"));
    }
    this.hot = i;
    this.segPane.classList.toggle("hovering", i !== null && this.segments.length <= DIM_LIMIT);
    if (i === null || !this.segEls[i]) return;
    const el = this.segEls[i];
    el.classList.add("hot");
    // The hovered segment always shows its whitespace, so spaces and newlines are visible.
    el.textContent = encodeWhitespace(this.segments[i].text);
    this.idEls[i].forEach((id) => id.classList.add("hot"));
  }
}
