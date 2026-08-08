(function () {
  const form = document.getElementById("register-form");
  if (!form) return;

  const table = document.getElementById("register-table");
  const saveButton = document.getElementById("save-button");
  const state = document.getElementById("save-state");
  const summary = document.getElementById("register-summary");
  const filter = document.getElementById("student-filter");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;

  const rows = () => Array.from(table.querySelectorAll("tbody tr"));

  function updateSummary() {
    const counts = { PRESENT: 0, ABSENT: 0, LATE: 0, EXCUSED: 0, unmarked: 0 };
    rows().forEach((row) => {
      const checked = row.querySelector("input[type=radio]:checked");
      if (checked) counts[checked.value] += 1;
      else counts.unmarked += 1;
    });
    summary.textContent =
      `${counts.PRESENT} present · ${counts.ABSENT} absent · ` +
      `${counts.LATE} late · ${counts.EXCUSED} excused` +
      (counts.unmarked ? ` · ${counts.unmarked} not marked` : "");
  }

  document.querySelectorAll("[data-mark-all]").forEach((button) => {
    button.addEventListener("click", () => {
      const status = button.dataset.markAll;
      rows().forEach((row) => {
        if (row.hidden) return;
        const radio = row.querySelector(`input[type=radio][value="${status}"]`);
        if (radio) radio.checked = true;
      });
      updateSummary();
    });
  });

  table.addEventListener("change", updateSummary);

  if (filter) {
    filter.addEventListener("input", () => {
      const term = filter.value.trim().toLowerCase();
      rows().forEach((row) => {
        row.hidden = term !== "" && !row.dataset.name.includes(term);
      });
    });
  }

  function collect() {
    return rows()
      .map((row) => {
        const checked = row.querySelector("input[type=radio]:checked");
        if (!checked) return null;
        const remark = row.querySelector("input[type=text]");
        return {
          student: Number(row.dataset.student),
          status: checked.value,
          remark: remark ? remark.value : "",
        };
      })
      .filter(Boolean);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const records = collect();
    if (records.length === 0) {
      state.textContent = "Mark at least one student before saving.";
      state.className = "mt-0.5 text-xs text-rose-600";
      return;
    }

    saveButton.disabled = true;
    saveButton.textContent = "Saving...";
    state.textContent = "Saving register...";
    state.className = "mt-0.5 text-xs text-slate-500";

    try {
      const response = await fetch(form.dataset.saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ records }),
      });
      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "The register could not be saved.");
      }

      state.textContent = `Saved ${data.saved} records at ${new Date().toLocaleTimeString()}.`;
      state.className = "mt-0.5 text-xs text-emerald-600";
    } catch (error) {
      state.textContent = error.message;
      state.className = "mt-0.5 text-xs text-rose-600";
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = "Save register";
    }
  });

  updateSummary();
})();
