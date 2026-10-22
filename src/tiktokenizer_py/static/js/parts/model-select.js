// The searchable model selector in the header.

export function modelSelectPart(ctx) {
  return {
    comboOpen: false,
    query: "",
    activeIndex: 0,

    // Popular repeats entries, so only the first option for the model is marked selected.
    get selectedKey() {
      return this.flatOptions.find((o) => o.id === this.model)?.key ?? "";
    },

    // Groups filtered by the search box. While searching, "Popular" is hidden because
    // its items repeat entries from the other groups.
    get filteredGroups() {
      const q = this.query.trim().toLowerCase();
      return ctx.page.catalogue.groups
        .filter((g) => !q || g.id !== "popular")
        .map((g) => ({
          ...g,
          options: g.items
            .filter((id) => !q || id.toLowerCase().includes(q))
            .map((id) => ({ id, key: `${g.id}:${id}`, entry: ctx.models.get(id) })),
        }))
        .filter((g) => g.options.length > 0);
    },

    get flatOptions() {
      return this.filteredGroups.flatMap((g) => g.options);
    },

    optionHint(entry) {
      if (entry.kind === "encoding") return entry.encoding === entry.base_encoding ? "" : "chat tokens";
      return entry.base_encoding;
    },

    openCombo() {
      this.query = "";
      this.comboOpen = true;
      const index = this.flatOptions.findIndex((o) => o.id === this.model);
      this.activeIndex = Math.max(index, 0);
      this.$nextTick(() => {
        this.$refs.comboSearch.focus();
        this.scrollActive();
      });
    },

    // Close when keyboard focus leaves the selector (Tab or Shift+Tab).
    comboFocusOut(event) {
      if (!event.currentTarget.contains(event.relatedTarget)) this.closeCombo(false);
    },

    closeCombo(refocus = true) {
      if (!this.comboOpen) return;
      this.comboOpen = false;
      if (refocus) this.$refs.comboTrigger.focus();
    },

    choose(id) {
      this.model = id;
      this.closeCombo();
    },

    moveActive(step) {
      const count = this.flatOptions.length;
      if (count === 0) return;
      this.activeIndex = (this.activeIndex + step + count) % count;
      this.scrollActive();
    },

    chooseActive() {
      const option = this.flatOptions[this.activeIndex];
      if (option) this.choose(option.id);
    },

    scrollActive() {
      this.$nextTick(() => {
        this.$refs.comboList?.querySelector(".combo-item.active")?.scrollIntoView({ block: "nearest" });
      });
    },

    optionDomId(option) {
      return `opt-${option.key.replace(/[^a-z0-9]/gi, "-")}`;
    },
  };
}
