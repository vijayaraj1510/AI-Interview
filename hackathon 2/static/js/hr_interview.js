(() => {
  const app = document.getElementById("hrApp");
  if (!app) return;

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const interviewId = Number(app.dataset.interview);
  const total = Number(app.dataset.total);
  const questionEl = document.getElementById("hrQuestion");
  const numberEl = document.getElementById("hrQuestionNumber");
  const progressEl = document.getElementById("hrProgress");
  const answerEl = document.getElementById("hrAnswer");
  const feedbackEl = document.getElementById("hrFeedback");
  const startButton = document.getElementById("startHrRecording");
  const stopButton = document.getElementById("stopHrRecording");
  const submitButton = document.getElementById("submitHr");
  const statusEl = document.getElementById("hrRecordingStatus");
  let currentQuestion = "";
  let recognition = null;
  let isListening = false;
  let finalTranscript = "";
  let interimTranscript = "";
  let submitting = false;

  const normalize = (text) => String(text || "").replace(/\s+/g, " ").trim();
  const setStatus = (message, active = false) => {
    statusEl.textContent = message;
    statusEl.classList.toggle("is-listening", active);
  };
  const setRecordingControls = (recording) => {
    startButton.classList.toggle("d-none", recording);
    stopButton.classList.toggle("d-none", !recording);
    submitButton.disabled = recording || !normalize(answerEl.value) || submitting;
  };
  const updateTranscript = () => {
    answerEl.value = normalize(`${finalTranscript} ${interimTranscript}`);
    submitButton.disabled = isListening || !normalize(answerEl.value) || submitting;
  };
  const appendFinal = (text) => {
    const next = normalize(text);
    const current = normalize(finalTranscript);
    if (!next || current === next || current.endsWith(next)) return;
    finalTranscript = normalize(`${current} ${next}`);
  };

  function createRecognition() {
    if (!Recognition || recognition) return;
    recognition = new Recognition();
    recognition.lang = "en-IN";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onstart = () => {
      setStatus("Listening... Speak your answer", true);
      setRecordingControls(true);
    };
    recognition.onresult = (event) => {
      interimTranscript = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript || "";
        if (result.isFinal) appendFinal(transcript);
        else interimTranscript = normalize(`${interimTranscript} ${transcript}`);
      }
      updateTranscript();
    };
    recognition.onerror = (event) => {
      const messages = {
        "not-allowed": "Microphone permission is required.",
        "no-speech": "No speech detected yet. Keep speaking when you are ready.",
        "audio-capture": "Microphone was disconnected.",
        network: "Speech recognition needs an internet connection.",
        aborted: "Recording stopped.",
      };
      setStatus(messages[event.error] || "Speech recognition could not continue.");
      if (event.error === "not-allowed" || event.error === "audio-capture") {
        isListening = false;
        setRecordingControls(false);
      }
    };
    recognition.onend = () => {
      interimTranscript = "";
      updateTranscript();
      if (isListening) {
        window.setTimeout(() => {
          try { recognition.start(); } catch (_) { /* The browser may already be restarting recognition. */ }
        }, 100);
      }
    };
  }

  async function request(path, body) {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || "Unable to continue the interview.");
    return data;
  }

  function resetAnswer() {
    isListening = false;
    recognition?.stop();
    finalTranscript = "";
    interimTranscript = "";
    answerEl.value = "";
    setStatus("Ready to record");
    setRecordingControls(false);
  }

  async function loadQuestion() {
    questionEl.textContent = "AI is preparing the next question...";
    resetAnswer();
    try {
      const data = await request("/hr-interview/question", { interview_id: interviewId });
      currentQuestion = data.question;
      questionEl.textContent = currentQuestion;
      numberEl.textContent = `Question ${data.number}`;
      progressEl.textContent = `${data.number} / ${total}`;
    } catch (error) {
      questionEl.textContent = error.message;
      setStatus("Unable to load a question");
    }
  }

  startButton.addEventListener("click", () => {
    if (!Recognition) return toast("Speech recognition is not supported in this browser.");
    if (isListening) return;
    createRecognition();
    finalTranscript = "";
    interimTranscript = "";
    answerEl.value = "";
    isListening = true;
    setStatus("Listening... Speak your answer", true);
    setRecordingControls(true);
    try { recognition.start(); } catch (_) { /* onend will safely restart if needed. */ }
  });

  stopButton.addEventListener("click", () => {
    isListening = false;
    interimTranscript = "";
    recognition?.stop();
    updateTranscript();
    setStatus("Recording stopped");
    setRecordingControls(false);
  });

  answerEl.addEventListener("input", () => {
    if (!isListening) {
      finalTranscript = normalize(answerEl.value);
      interimTranscript = "";
      setRecordingControls(false);
    }
  });

  submitButton.addEventListener("click", async () => {
    if (submitting || isListening || !normalize(answerEl.value)) return;
    submitting = true;
    submitButton.disabled = true;
    submitButton.textContent = "AI is evaluating your answer...";
    try {
      const data = await request("/hr-interview/answer", { interview_id: interviewId, answer: normalize(answerEl.value) });
      feedbackEl.innerHTML = `<div class="mini-item"><b>Score: ${data.score || 0}%</b><p class="mb-0">${data.message || data.feedback || ""}</p></div>`;
      if (data.done) window.location.assign(data.result_url);
      else await loadQuestion();
    } catch (error) {
      toast(error.message);
      setRecordingControls(false);
    } finally {
      submitting = false;
      submitButton.textContent = "Submit Answer";
      if (!isListening) setRecordingControls(false);
    }
  });

  createRecognition();
  loadQuestion();
})();
