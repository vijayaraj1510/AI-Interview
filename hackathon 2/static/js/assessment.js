const form = document.getElementById("assessmentForm");
if (form) {
  const cards = [...document.querySelectorAll(".question-card")];
  const dots = [...document.querySelectorAll(".q-dot")];
  const timer = document.getElementById("timer");
  const timeTaken = document.getElementById("timeTaken");
  let index = 0;
  let submitted = false;
  const totalSeconds = Math.max(1, Number(form.dataset.minutes || 10)) * 60;
  const started = Date.now();
  function show(i) {
    index = Math.max(0, Math.min(cards.length - 1, i));
    cards.forEach((card, n) => card.classList.toggle("d-none", n !== index));
    dots.forEach((dot, n) => dot.classList.toggle("active", n === index));
  }
  function tick() {
    const elapsed = Math.floor((Date.now() - started) / 1000);
    const left = Math.max(0, totalSeconds - elapsed);
    timeTaken.value = elapsed;
    timer.textContent = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;
    if (left <= 0 && !submitted) {
      submitted = true;
      form.requestSubmit();
    }
  }
  dots.forEach((dot, i) => dot.addEventListener("click", () => show(i)));
  document.getElementById("prevBtn")?.addEventListener("click", () => show(index - 1));
  document.getElementById("nextBtn")?.addEventListener("click", () => show(index + 1));
  form.addEventListener("change", (event) => {
    if (event.target.type === "radio") dots[index]?.classList.add("answered");
  });
  form.addEventListener("input", (event) => {
    if (event.target.classList.contains("technical-answer") && event.target.value.trim()) dots[index]?.classList.add("answered");
  });
  form.addEventListener("submit", (event) => {
    if (submitted) return;
    if (!confirm("Submit this assessment now?")) event.preventDefault();
    submitted = true;
  });
  show(0);
  tick();
  setInterval(tick, 1000);
}
