(() => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const app = document.getElementById("spokenApp");
  if (!app) return;
  const transcriptEl = document.getElementById("transcript");
  const statusEl = document.getElementById("speechStatus");
  const counterEl = document.getElementById("transcriptCounter");
  const questionEl = document.getElementById("spokenQuestion");
  const questionNumberEl = document.getElementById("spokenQuestionNumber");
  const progressEl = document.getElementById("spokenProgress");
  const practiceEl = document.getElementById("spokenPractice");
  const welcomeEl = document.getElementById("spokenWelcome");
  let recognition = null;
  let finalTranscript = "";
  let isListening = false;
  let startedAt = 0;
  let submitting = false;

  const normalize = (text) => String(text || "").replace(/\s+/g, " ").trim();
  const updateTranscript = (interim = "") => {
    if (!transcriptEl) return;
    transcriptEl.value = normalize(`${finalTranscript} ${interim}`);
    if (counterEl) counterEl.textContent = `${transcriptEl.value.length} / 4000`;
  };
  const setStatus = (message, listening = false) => {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.classList.toggle("is-listening", listening);
  };
  const resetAnswer = () => {
    isListening = false;
    recognition?.stop();
    finalTranscript = "";
    startedAt = 0;
    updateTranscript();
    setStatus("Ready to listen");
  };
  const loadQuestion = (data) => {
    questionEl.textContent = data.question;
    questionNumberEl.textContent = `Question ${data.number} of ${data.total}`;
    progressEl.textContent = `${data.number} / ${data.total}`;
    resetAnswer();
    practiceEl.classList.remove("d-none");
    welcomeEl.classList.add("d-none");
  };
  const appendFinal = (text) => {
    const next = normalize(text);
    if (!next || finalTranscript === next || finalTranscript.endsWith(next)) return;
    finalTranscript = normalize(`${finalTranscript} ${next}`);
  };

  if (SpeechRecognition && transcriptEl) {
    recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onstart = () => setStatus("Listening...", true);
    recognition.onresult = (event) => {
      let interim = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) appendFinal(result[0]?.transcript);
        else interim = normalize(`${interim} ${result[0]?.transcript || ""}`);
      }
      updateTranscript(interim);
    };
    recognition.onerror = (event) => {
      const messages = { "not-allowed": "Microphone permission is required.", "no-speech": "Please speak clearly.", "audio-capture": "Microphone was disconnected.", network: "Speech recognition needs an internet connection.", aborted: "Recording stopped." };
      setStatus(messages[event.error] || "Speech recognition could not start.");
      if (["not-allowed", "audio-capture"].includes(event.error)) isListening = false;
    };
    recognition.onend = () => {
      updateTranscript();
      if (isListening && !submitting) window.setTimeout(() => { try { recognition.start(); } catch (_) {} }, 150);
    };
  }

  document.getElementById("startSpoken")?.addEventListener("click", async () => {
    const button = document.getElementById("startSpoken");
    button.disabled = true;
    try {
      const response = await fetch("/spoken/start", { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || "Unable to start practice.");
      loadQuestion(data);
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  });
  document.getElementById("startSpeech")?.addEventListener("click", () => {
    if (!recognition) return toast("Speech recognition is not supported in this browser.");
    if (!startedAt) startedAt = Date.now();
    isListening = true;
    try { recognition.start(); } catch (_) { setStatus("Listening...", true); }
  });
  document.getElementById("stopSpeech")?.addEventListener("click", () => { isListening = false; recognition?.stop(); setStatus("Stopped"); });
  document.getElementById("clearSpeech")?.addEventListener("click", resetAnswer);
  transcriptEl?.addEventListener("input", () => { finalTranscript = normalize(transcriptEl.value); updateTranscript(); });

  async function submitAnswer(skip = false) {
    if (submitting) return;
    const transcript = skip ? "" : normalize(transcriptEl.value);
    if (!skip && !transcript) return toast("Record or type an answer, or choose Skip.");
    const button = skip ? document.getElementById("skipSpoken") : document.getElementById("submitSpoken");
    submitting = true;
    isListening = false;
    recognition?.stop();
    button.disabled = true;
    button.textContent = "Evaluating your answer...";
    try {
      const response = await fetch("/spoken/answer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ transcript, duration: startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0 }) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || "Unable to save this answer.");
      if (data.done) return window.location.assign(data.result_url);
      setStatus("Loading next question...");
      loadQuestion(data);
    } catch (error) { toast(error.message); }
    finally {
      submitting = false;
      button.disabled = false;
      button.textContent = skip ? "Skip" : "Submit Answer";
    }
  }
  document.getElementById("submitSpoken")?.addEventListener("click", () => submitAnswer());
  document.getElementById("skipSpoken")?.addEventListener("click", () => submitAnswer(true));
})();
