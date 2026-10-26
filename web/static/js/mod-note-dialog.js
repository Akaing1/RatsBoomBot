(() => {
    const dialog = document.querySelector("[data-mod-note-dialog]");
    const opener = document.querySelector("[data-mod-note-open]");
    if (!dialog || !opener) return;
    const form = dialog.querySelector("[data-mod-note-form]");
    const status = dialog.querySelector("[data-mod-note-status]");
    let pending = false;
    let submissionId = null;
    opener.addEventListener("click", () => dialog.showModal());
    dialog.querySelector("[data-mod-note-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => opener.focus());
    form?.addEventListener("input", () => { submissionId = null; status.textContent = ""; });
    form?.addEventListener("submit", async event => {
        event.preventDefault();
        if (pending) return;
        if (!form.elements.notes.value.trim()) { status.textContent = "Write a note before saving."; return; }
        submissionId ||= crypto.randomUUID().replaceAll("-", "");
        const body = new FormData(form);
        body.set("submission_id", submissionId);
        pending = true;
        const controls = [...form.querySelectorAll("input, textarea, button")];
        controls.forEach(control => control.disabled = true);
        status.textContent = "Saving…";
        try {
            const response = await fetch(form.action, {method: "POST", body, headers: {Accept: "application/json"}});
            const result = await response.json();
            if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not save this note.");
            form.reset();
            submissionId = null;
            status.textContent = "Saved to the streamer's For You notes.";
        } catch (error) {
            status.textContent = `${error.message || "Could not confirm the save."} Your draft is still here; retry to confirm the save.`;
        } finally {
            pending = false;
            controls.forEach(control => control.disabled = false);
        }
    });
})();
