document.getElementById("selectAll")?.addEventListener("change", (event) => {
  document.querySelectorAll('input[name="ids"]').forEach((box) => { box.checked = event.target.checked; });
});
document.getElementById("bulkForm")?.addEventListener("submit", (event) => {
  if (!document.querySelector('input[name="ids"]:checked')) {
    event.preventDefault();
    toast("Select at least one question.");
    return;
  }
  if (!confirm("Apply this bulk action?")) event.preventDefault();
});
function updatePreview() {
  document.querySelectorAll(".preview-input").forEach((input) => {
    const target = document.getElementById(input.dataset.preview);
    if (target) target.textContent = input.value || target.textContent;
  });
}
document.querySelectorAll(".preview-input").forEach((input) => input.addEventListener("input", updatePreview));
updatePreview();
