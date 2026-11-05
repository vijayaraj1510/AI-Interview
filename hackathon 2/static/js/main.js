const sidebar = document.getElementById("sidebar");
let installPrompt;
document.getElementById("menuToggle")?.addEventListener("click", () => sidebar?.classList.toggle("open"));
document.getElementById("themeToggle")?.addEventListener("click", () => {
  document.body.classList.toggle("light-mode");
  toast("Theme preference updated.");
});
function toast(message) {
  const box = document.getElementById("toastBox");
  if (!box) return;
  const node = document.createElement("div");
  node.className = "toast align-items-center text-bg-dark border-0 show";
  node.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  box.appendChild(node);
  setTimeout(() => node.remove(), 3200);
}
document.querySelectorAll(".confirm-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    if (!confirm("Please confirm this action.")) event.preventDefault();
  });
});
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/service-worker.js"));
}
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  document.getElementById("installApp")?.classList.remove("d-none");
});
document.getElementById("installApp")?.addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  document.getElementById("installApp")?.classList.add("d-none");
});
