(function () {
  const textarea = document.getElementById("body-field");
  const preview = document.getElementById("live-preview");
  const notesDataEl = document.getElementById("notes-data");
  if (!textarea || !preview) return;

  const NOTES = notesDataEl ? JSON.parse(notesDataEl.textContent) : [];

  const PREVIEW_DEBOUNCE_MS = 250;
  let previewTimer = null;

  function renderPreview() {
    fetch("/preview", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "body=" + encodeURIComponent(textarea.value),
    })
      .then((r) => r.text())
      .then((html) => {
        preview.innerHTML = html;
      })
      .catch(() => {});
  }

  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderPreview, PREVIEW_DEBOUNCE_MS);
  }

  // --- [[wikilink autocomplete ---

  const dropdown = document.createElement("div");
  dropdown.className = "wikilink-autocomplete";
  dropdown.style.display = "none";
  document.body.appendChild(dropdown);

  let matches = [];
  let activeIndex = -1;

  function closeAutocomplete() {
    dropdown.style.display = "none";
    matches = [];
    activeIndex = -1;
  }

  // Look backward from the caret for an unclosed "[[" on the current line -
  // that's the span of text the autocomplete is filtering on and will
  // replace once a note is picked.
  function currentQuery() {
    const caret = textarea.selectionStart;
    const upToCaret = textarea.value.slice(0, caret);
    const openIdx = upToCaret.lastIndexOf("[[");
    if (openIdx === -1) return null;
    const between = upToCaret.slice(openIdx + 2);
    if (between.includes("]]") || between.includes("\n") || between.includes("[")) return null;
    return { start: openIdx + 2, query: between };
  }

  function positionDropdown() {
    // A pixel-accurate caret position inside a <textarea> needs a mirrored
    // shadow element; skipped here for a personal single-user tool - anchoring
    // just under the textarea is close enough without that extra machinery.
    const rect = textarea.getBoundingClientRect();
    dropdown.style.left = rect.left + window.scrollX + "px";
    dropdown.style.top = rect.bottom + window.scrollY + 4 + "px";
    dropdown.style.width = Math.min(rect.width, 360) + "px";
  }

  function renderDropdown() {
    dropdown.innerHTML = "";
    matches.forEach((note, i) => {
      const item = document.createElement("div");
      item.className = "wikilink-option" + (i === activeIndex ? " active" : "");
      item.textContent = note.title;
      item.addEventListener("mousedown", (e) => {
        e.preventDefault(); // keep textarea focus/selection so selectMatch's caret math holds
        selectMatch(i);
      });
      dropdown.appendChild(item);
    });
  }

  function selectMatch(i) {
    const state = currentQuery();
    if (!state || !matches[i]) {
      closeAutocomplete();
      return;
    }
    const note = matches[i];
    const insertion = "[[" + note.id + "|" + note.title + "]]";
    const before = textarea.value.slice(0, state.start - 2);
    const after = textarea.value.slice(textarea.selectionStart);
    textarea.value = before + insertion + after;
    const caretPos = before.length + insertion.length;
    textarea.setSelectionRange(caretPos, caretPos);
    closeAutocomplete();
    textarea.focus();
    schedulePreview();
  }

  function updateAutocomplete() {
    const state = currentQuery();
    if (!state) {
      closeAutocomplete();
      return;
    }

    const q = state.query.trim().toLowerCase();
    matches = NOTES.filter((n) => n.title.toLowerCase().includes(q)).slice(0, 8);
    if (!matches.length) {
      closeAutocomplete();
      return;
    }

    activeIndex = 0;
    positionDropdown();
    renderDropdown();
    dropdown.style.display = "block";
  }

  textarea.addEventListener("input", () => {
    schedulePreview();
    updateAutocomplete();
  });

  textarea.addEventListener("keydown", (e) => {
    if (dropdown.style.display !== "block") return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, matches.length - 1);
      renderDropdown();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      renderDropdown();
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      selectMatch(activeIndex);
    } else if (e.key === "Escape") {
      closeAutocomplete();
    }
  });

  textarea.addEventListener("blur", () => {
    // Give a mousedown-triggered selectMatch a chance to run first (it
    // calls preventDefault precisely so this blur only fires for a
    // genuine "left the field", e.g. tabbing to another input).
    setTimeout(closeAutocomplete, 150);
  });

  window.addEventListener("resize", () => {
    if (dropdown.style.display === "block") positionDropdown();
  });

  // Ctrl/Cmd+S should save from anywhere in the form, not just the body field.
  document.addEventListener("keydown", (e) => {
    if ((e.key === "s" || e.key === "S") && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      const form = document.getElementById("note-form");
      if (form) form.requestSubmit();
    }
  });

  renderPreview();
})();
