const filters = document.querySelector(".filters");
const search = document.getElementById("theme-search");
const mode = document.getElementById("theme-mode");
const count = document.getElementById("theme-count");
const noMatches = document.getElementById("no-matches");
const groups = Array.from(document.querySelectorAll(".theme-list"), (section) => ({
  section,
  mode: section.dataset.mode,
  cards: Array.from(section.querySelectorAll("li"), (card) => ({
    card,
    name: card.querySelector("h3").textContent.toLowerCase(),
  })),
}));
const total = groups.reduce((sum, group) => sum + group.cards.length, 0);

function filterThemes() {
  const term = search.value.trim().toLowerCase();
  let visible = 0;
  for (const group of groups) {
    const matchesMode = mode.value === "all" || group.mode === mode.value;
    let matches = 0;
    for (const { card, name } of group.cards) {
      card.hidden = !matchesMode || !name.includes(term);
      if (!card.hidden) matches += 1;
    }
    group.section.hidden = matches === 0;
    visible += matches;
  }
  count.textContent = `Showing ${visible} of ${total} themes`;
  noMatches.hidden = visible !== 0;
}

for (const link of document.querySelectorAll(".jump-links a")) {
  link.addEventListener("click", () => {
    const group = groups.find(({ section }) => `#${section.id}` === link.hash);
    if (group && group.section.hidden) {
      search.value = "";
      mode.value = group.mode;
      filterThemes();
    }
  });
}
search.addEventListener("input", filterThemes);
mode.addEventListener("change", filterThemes);
filters.hidden = false;
filterThemes();
