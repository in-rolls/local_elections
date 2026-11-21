const filters = document.querySelector("#filters");
const selects = Array.from(filters.querySelectorAll("select"));
const rows = Array.from(document.querySelectorAll("tbody tr"));
const count = document.querySelector("#record-count");

function filterTable() {
  let matches = 0;
  for (const row of rows) {
    row.hidden = !selects.every((select, i) =>
      select.value === "" || row.cells[i].textContent === select.value
    );
    if (!row.hidden) matches += 1;
  }
  count.textContent = matches === 0
    ? "No seat records match these filters."
    : `Showing ${matches} of ${rows.length} state, year, and office combinations.`;
}

filters.hidden = false;
filters.addEventListener("change", filterTable);
filterTable();

const copy = document.querySelector("#copy");
if (navigator.clipboard) {
  copy.hidden = false;
  copy.addEventListener("click", async () => {
    const citation = document.querySelector("#cite-text");
    try {
      await navigator.clipboard.writeText(citation.textContent);
      copy.textContent = "Copied";
      document.querySelector("#copy-status").textContent = "Citation copied.";
    } catch {
      const range = document.createRange();
      range.selectNodeContents(citation);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.querySelector("#copy-status").textContent = "Citation selected. Use your copy command.";
    }
  });
}
