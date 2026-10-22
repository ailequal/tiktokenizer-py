// tiktokenizer-py UI. Alpine.js handles the controls; the token panes, the chunk list and the
// merge replay are built with plain DOM calls inside x-ignore containers, because a long prompt
// can produce tens of thousands of elements and Alpine's tracking of them would be slow.
//
// The page is one Alpine component assembled from parts (parts/*.js). Each part returns plain
// state, getters and methods; they share non-reactive data (big payloads, timers, request
// sequence numbers) through `ctx`, which stays out of Alpine's proxies.

import { modelFromUrl } from "./lib/share.js";
import { costPart } from "./parts/cost.js";
import { decodePart } from "./parts/decode.js";
import { howItWorksPart } from "./parts/how-it-works.js";
import { inputPart } from "./parts/input.js";
import { modelSelectPart } from "./parts/model-select.js";
import { panelsPart } from "./parts/panels.js";
import { sharingPart } from "./parts/sharing.js";
import { themePart } from "./parts/theme.js";
import { ChunkList } from "./views/how-it-works.js";
import { TokenPanes } from "./views/token-panes.js";

// Merge the parts, keeping getters as getters (a spread would evaluate them once).
function compose(...parts) {
  const component = {};
  for (const part of parts) {
    for (const [name, descriptor] of Object.entries(Object.getOwnPropertyDescriptors(part))) {
      if (name in component) throw new Error(`"${name}" is defined by two parts`);
      Object.defineProperty(component, name, descriptor);
    }
  }
  return component;
}

document.addEventListener("alpine:init", () => {
  const page = JSON.parse(document.getElementById("page-data").textContent);
  const models = new Map(page.catalogue.models.map((m) => [m.id, m]));
  const introText = page.examples.find((e) => e.id === page.intro_example)?.text ?? "";

  window.Alpine.data("tokenizer", () => {
    const ctx = {
      page,
      models,
      introText,
      panes: null,
      chunkList: null,
      timer: null,
      statusTimer: null,
      inflight: null,
      extrasInflight: null,
      sequence: 0,
      mergeSequence: 0,
      detailSequence: 0,
      lastTokens: [],
      lastSegments: [],
      lastChunks: [],
    };

    return compose(
      {
        page,
        model: modelFromUrl(models, page.catalogue.default),

        async init() {
          // The span containers carry x-ignore, so Alpine does not track the thousands of spans
          // they hold (tracking them makes replacing a large result quadratic).
          ctx.panes = new TokenPanes(
            document.getElementById("segments-body"),
            document.getElementById("ids-body"),
            (i) => this.selectSegment(i),
          );
          ctx.chunkList = new ChunkList(document.getElementById("chunks-body"), (i) => this.selectChunk(i));
          await this.restoreFromLink();
          this.watchCost();
          this.watchInput();
          this.schedule(0);
        },
      },
      inputPart(ctx),
      modelSelectPart(ctx),
      howItWorksPart(ctx),
      decodePart(ctx),
      costPart(ctx),
      sharingPart(ctx),
      panelsPart(ctx),
      themePart(),
    );
  });
});
