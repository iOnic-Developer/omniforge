/* Progressive enhancement only. No analytics, storage, network or service worker. */
const status = document.getElementById("copy-status");
for (const button of document.querySelectorAll("[data-copy]")) {
  button.hidden = false;
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copy);
    if (!target || !status) return;
    try {
      if (!navigator.clipboard?.writeText)
        throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(target.textContent);
      status.textContent =
        "Command copied. Review the local access and API key requirements before running it.";
    } catch {
      status.textContent =
        "Clipboard unavailable. Select and copy the command directly from the code block.";
    }
  });
}
