const state = { currentView: "overview", running: false, selectedArticle: 0, backendOnline: false, currentQuestion: null, learning: null, quiz: null, opportunities: null };
const panels = [...document.querySelectorAll("[data-panel]")];
const navItems = [...document.querySelectorAll("[data-view]")];
const breadcrumb = document.querySelector("#breadcrumb-current");
const pageTitle = document.querySelector("#page-title");
const toast = document.querySelector("#toast");
const runButton = document.querySelector("#run-button");

async function apiRequest(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
}

const articleData = [];

const titles = {
  overview: { breadcrumb: "Overview", title: "Your technical edge,<br /><em>one day sharper.</em>", subtitle: "A focused read on the systems, signals, and skills that move your career forward." },
  workflow: { breadcrumb: "Agent workflow", title: "See the loop,<br /><em>step by step.</em>", subtitle: "Follow how DailyTechUpgradeAgent turns technical signals into an improvement loop." },
  radar: { breadcrumb: "Technical radar", title: "Signals worth<br /><em>your attention.</em>", subtitle: "Grounded developments across AI, research, SRE, DevOps, and software engineering." },
  opportunities: { breadcrumb: "Opportunity scout", title: "Find your next<br /><em>career move.</em>", subtitle: "Find source-backed internships, prepare for the role, and track your progress." },
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 3600);
}

function setView(view) {
  if (!titles[view]) return;
  state.currentView = view;
  navItems.forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
  panels.forEach((panel) => {
    const active = panel.dataset.panel === view;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", String(!active));
  });
  breadcrumb.textContent = titles[view].breadcrumb;
  pageTitle.innerHTML = titles[view].title;
  document.querySelector("#page-subtitle").textContent = titles[view].subtitle;
  document.querySelector("#agent-heading").textContent = view === "opportunities" ? "NEXTLEVELPERSONALCOACHFORCAREERLEVEL" : "DAILYTECHUPGRADEAGENT";
  document.querySelector("#run-heading").textContent = view === "opportunities" ? "DAILY OPPORTUNITY RUN" : "MORNING RUN";
  runButton.hidden = view === "opportunities";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll("[data-view-target]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});
navItems.forEach((item) => item.addEventListener("click", () => {
  setView(item.dataset.view);
  if (item.dataset.view === "opportunities") syncOpportunities();
}));
setView(state.currentView);

document.querySelectorAll(".agent-card").forEach((agent) => {
  agent.addEventListener("click", () => {
    if (agent.dataset.agent === "coach") {
      document.querySelectorAll(".agent-card").forEach((item) => item.classList.remove("active"));
      agent.classList.add("active");
      setView("opportunities");
      syncOpportunities();
      return;
    }
    document.querySelectorAll(".agent-card").forEach((item) => item.classList.remove("active"));
    agent.classList.add("active");
    setView("overview");
    showToast("DailyTechUpgradeAgent is your active technical coworker.");
  });
});

document.querySelectorAll(".article-row").forEach((article) => {
  article.addEventListener("click", () => {
    state.selectedArticle = Number(article.dataset.article);
    document.querySelectorAll(".article-row").forEach((row) => row.classList.remove("selected"));
    article.classList.add("selected");
    renderArticleDetail(state.selectedArticle);
    showToast(`Brief selected · ${articleData[state.selectedArticle]?.source || "live source"}`);
  });
});

function articleTagClass(article) {
  if (article.tagClass) return article.tagClass;
  if (article.lane === "sre_devops_support") return "tag-blue";
  if ((article.tag || "").toLowerCase().includes("anthropic")) return "tag-purple";
  return "tag-teal";
}

function renderArticleList(articles) {
  if (!articles?.length) return;
  articleData.splice(0, articleData.length, ...articles.slice(0, 3).map((article) => ({
    ...article,
    tagClass: articleTagClass(article),
    readTime: article.readTime || article.read_time || "fresh signal",
    action: article.action || article.why_it_matters || "Turn this insight into a small practice task.",
  })));
  document.querySelectorAll(".article-row").forEach((row, index) => {
    const article = articleData[index];
    if (!article) return;
    row.querySelector(".article-number").textContent = String(index + 1).padStart(2, "0");
    row.querySelector(".article-meta .tag").className = `tag ${article.tagClass}`;
    row.querySelector(".article-meta .tag").textContent = article.tag || "LIVE SOURCE";
    row.querySelector(".article-meta span:nth-child(2)").textContent = article.readTime;
    row.querySelector("h3").textContent = article.title;
    row.querySelector("p").textContent = article.summary;
    row.querySelector(".article-footer span").textContent = article.source;
  });
  document.querySelectorAll(".article-row").forEach((row) => row.classList.remove("selected"));
  document.querySelector(`.article-row[data-article="${state.selectedArticle}"]`)?.classList.add("selected");
  renderArticleDetail(state.selectedArticle);
}

function renderArticleDetail(index) {
  const article = articleData[index];
  if (!article) return;
  const grounded = Boolean(article.grounded || article.reference);
  const kicker = document.querySelector("#detail-kicker");
  if (kicker) kicker.textContent = grounded ? "Selected article · live source summary" : "Selected article · source unavailable";
  document.querySelector("#detail-heading").textContent = article.title;
  document.querySelector("#detail-meta").innerHTML = `<span class="tag ${article.tagClass}">${article.tag}</span><span>${article.source}</span><span>${article.readTime}</span>`;
  document.querySelector("#detail-summary").textContent = article.summary;
  document.querySelector("#detail-takeaways").innerHTML = article.takeaways.map((takeaway) => `<li>${takeaway}</li>`).join("");
  document.querySelector("#detail-action-text").textContent = article.action || article.why_it_matters || "Turn this insight into a small practice task.";
  document.querySelector("#detail-reference").textContent = grounded ? `Reference · ${article.source}` : "No source loaded";
  const referenceLink = document.querySelector("#reference-link");
  if (referenceLink) {
    referenceLink.href = article.reference || "#";
    referenceLink.hidden = !article.reference;
  }
}

function applyDashboard(data) {
  if (!data) return;
  if (data.learning) applyLearning(data.learning);
  renderArticleList(data.articles || []);
  renderRadar(data.articles || []);
}

function renderRadar(articles) {
  const radarArticles = articles.filter((article) => article.lane === "sre_devops_support").slice(0, 4);
  document.querySelectorAll(".radar-card").forEach((card, index) => {
    const article = radarArticles[index];
    if (!article) {
      card.hidden = true;
      return;
    }
    card.hidden = false;
    const tag = card.querySelector(".tag");
    const score = card.querySelector(".radar-score");
    const heading = card.querySelector("h3");
    const summary = card.querySelector("p");
    const sourceLink = card.querySelector(".radar-source-link");
    if (tag) {
      tag.className = `tag ${articleTagClass(article)}`;
      tag.textContent = article.source || "LIVE SOURCE";
    }
    if (score) score.textContent = `${article.source_type === "rss_atom" ? "grounded" : "source"}`;
    if (heading) heading.textContent = article.title;
    if (summary) summary.textContent = article.summary;
    if (sourceLink) {
      sourceLink.href = article.reference || "#";
      sourceLink.hidden = !article.reference;
    }
  });
}

function applyLearning(learning) {
  state.learning = learning;
  const streak = document.querySelector("#learning-streak");
  const trend = document.querySelector("#learning-trend");
  const note = document.querySelector("#learning-note");
  const days = document.querySelector("#learning-days");
  if (streak) streak.textContent = String(learning.streak_days || 0).padStart(2, "0");
  if (trend) {
    const delta = Number(learning.week_delta || 0);
    trend.textContent = `${delta >= 0 ? "↗" : "↘"} ${Math.abs(delta)} days`;
    trend.classList.toggle("up", delta >= 0);
    trend.classList.toggle("neutral", delta < 0);
  }
  if (note) {
    note.innerHTML = learning.completed_today
      ? `Today’s 3-question quiz is complete${learning.quiz_score == null ? "" : ` · ${learning.quiz_score}/100`}. Keep the streak alive tomorrow.`
      : "Complete today’s 3-question quiz to start or continue your streak.";
  }
  if (days) days.innerHTML = (learning.completed_days || []).map((complete, index, values) => `<span class="${complete ? "done" : ""} ${index === values.length - 1 ? "today" : ""}"></span>`).join("");
}

function showLearningChallenge(learning) {
  state.learning = learning;
  const challenge = learning.challenge || {};
  document.querySelector("#challenge-source").textContent = `Grounded article · ${challenge.source_title || "today’s technical brief"} · ${challenge.source || "source"}`;
  const questions = challenge.questions || [{ prompt: challenge.prompt || "Choose one technical idea from today’s brief.", options: ["Option unavailable"] }];
  const savedAnswers = (learning.quiz_results || []).map((result) => result.selected_option);
  state.quiz = { questions, answers: questions.map((_, index) => savedAnswers[index] ?? null), index: 0 };
  const result = document.querySelector("#challenge-result");
  if (result) {
    result.hidden = !learning.completed_today;
    result.textContent = learning.completed_today ? `Today’s quiz is already complete${learning.quiz_score == null ? "" : ` · score ${learning.quiz_score}/100`}.` : "";
  }
  renderQuizQuestion();
  renderQuizReview(learning);
  document.querySelector("#challenge-modal").hidden = false;
  document.querySelector("#challenge-options input")?.focus();
}

function renderQuizQuestion() {
  const quiz = state.quiz;
  if (!quiz) return;
  const question = quiz.questions[quiz.index] || quiz.questions[0];
  const completed = Boolean(state.learning?.completed_today);
  const progress = document.querySelector("#challenge-progress");
  const prompt = document.querySelector("#challenge-prompt");
  const options = document.querySelector("#challenge-options");
  const previous = document.querySelector("#quiz-previous");
  const next = document.querySelector("#complete-learning");
  if (progress) { progress.textContent = `Question ${quiz.index + 1} of ${quiz.questions.length}`; progress.hidden = completed; }
  if (prompt) { prompt.textContent = question.prompt; prompt.hidden = completed; }
  if (options) {
    options.hidden = completed;
    options.innerHTML = (question.options || []).map((option, index) => `<label class="quiz-option"><input type="radio" name="daily-quiz-option" value="${index}" ${quiz.answers[quiz.index] === index ? "checked" : ""} ${completed ? "disabled" : ""}><span class="quiz-option-marker">${String.fromCharCode(65 + index)}</span><span>${escapeHtml(option)}</span></label>`).join("");
    options.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => { quiz.answers[quiz.index] = Number(input.value); });
    });
  }
  if (previous) { previous.disabled = completed || quiz.index === 0; previous.hidden = completed; }
  if (next) {
    next.disabled = completed;
    next.hidden = completed;
    next.innerHTML = quiz.index === quiz.questions.length - 1 ? "Submit quiz <span>↗</span>" : "Next question <span>↗</span>";
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[character]));
}

function renderQuizReview(learning) {
  const review = document.querySelector("#quiz-review");
  if (!review) return;
  if (!learning.completed_today || !state.quiz) {
    review.hidden = true;
    review.innerHTML = "";
    return;
  }
  review.hidden = false;
  review.innerHTML = (learning.quiz_results || []).map((result, index) => {
    const question = state.quiz.questions[index] || {};
    const selected = question.options?.[result.selected_option] || "No answer";
    const correct = question.options?.[result.correct_option] || "Unavailable";
    return `<div class="quiz-review-item ${result.correct ? "is-correct" : "is-incorrect"}><div><strong>Question ${index + 1}</strong><span>${result.correct ? "Correct" : "Incorrect"}</span></div><p>Your answer: ${escapeHtml(selected)}</p>${result.correct ? "" : `<p>Correct answer: ${escapeHtml(correct)}</p>`}</div>`;
  }).join("");
}

async function syncOpportunities() {
  try {
    const data = await apiRequest("/api/opportunities");
    state.opportunities = data;
    renderOpportunities(data);
  } catch {
    showToast("The opportunity scout backend is unavailable.");
  }
}

function renderOpportunities(data) {
  const status = document.querySelector("#opportunity-status");
  const count = document.querySelector("#opportunity-count");
  const list = document.querySelector("#opportunity-list");
  if (!list) return;
  const jobs = data.opportunities || [];
  if (status) {
    status.textContent = data.source_status === "configured"
      ? `${data.configured_sources.length} public source feeds configured · ${jobs.length} grounded internship matches`
      : "No public job feeds configured yet. Add JOB_FEEDS in your environment, then run a scan. LinkedIn, Indeed, and Glassdoor should be connected through an official API, export, or alert feed.";
  }
  if (count) count.textContent = `${jobs.length} match${jobs.length === 1 ? "" : "es"}`;
  if (!jobs.length) {
    list.innerHTML = `<div class="opportunity-empty compact"><span class="opportunity-empty-icon">⌁</span><h3>No grounded postings yet</h3><p>The scout will only show source-backed opportunities after a compliant public feed is configured.</p></div>`;
    document.querySelector("#opportunity-detail").innerHTML = `<div class="opportunity-empty"><span class="opportunity-empty-icon">△</span><h3>Preparation follows selection</h3><p>Once a grounded posting is found, select it to generate technical questions, a coding exercise, and an interview scenario.</p></div>`;
    return;
  }
  list.innerHTML = jobs.map((job) => `<article class="opportunity-card ${data.selected?.id === job.id ? "selected" : ""}" data-opportunity-id="${escapeHtml(job.id)}"><div class="opportunity-card-top"><span class="tag tag-blue">${escapeHtml(job.source)}</span><strong>${job.match_score}% match</strong></div><h4>${escapeHtml(job.title)}</h4><p>${escapeHtml(job.why_match)}</p><div class="opportunity-card-footer"><span>${escapeHtml(job.matched_role)}</span><button class="text-button" type="button" data-select-opportunity="${escapeHtml(job.id)}">Prepare ↗</button></div></article>`).join("");
  list.querySelectorAll("[data-select-opportunity]").forEach((button) => button.addEventListener("click", () => selectOpportunity(button.dataset.selectOpportunity)));
  list.querySelectorAll(".opportunity-card").forEach((card) => card.addEventListener("click", (event) => {
    if (!event.target.closest("button")) selectOpportunity(card.dataset.opportunityId);
  }));
  renderOpportunityDetail(data);
}

function renderOpportunityDetail(data) {
  const detail = document.querySelector("#opportunity-detail");
  const job = data.selected;
  const prep = data.prep;
  if (!detail || !job || !prep) return;
  detail.innerHTML = `<div class="opportunity-detail-header"><div><p class="eyebrow">SELECTED OPPORTUNITY · ${escapeHtml(job.source)}</p><h3>${escapeHtml(job.title)}</h3><p>${escapeHtml(job.description || "Grounded job description available at the source.")}</p></div><strong class="match-score">${job.match_score}%</strong></div><div class="opportunity-detail-actions"><a class="text-button" href="${escapeHtml(job.reference)}" target="_blank" rel="noopener noreferrer">Open full posting ↗</a><button class="outline-button" data-opportunity-status="saved" type="button">Save</button><button class="outline-button" data-opportunity-status="applied" type="button">Mark applied</button></div><div class="prep-block"><p class="eyebrow">PERSONALIZED PREPARATION</p><h4>Technical questions</h4><ol>${prep.technical_questions.map((question) => `<li>${escapeHtml(question)}</li>`).join("")}</ol><h4>Coding exercise</h4><p>${escapeHtml(prep.coding_exercise)}</p><h4>Interview scenario</h4><p>${escapeHtml(prep.interview_scenario)}</p><h4>Action plan</h4><ul>${prep.learning_plan.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul></div><div class="prep-response"><p class="eyebrow">PRACTICE WITH YOUR COACH</p><p id="prep-prompt">${escapeHtml(prep.technical_questions[0])}</p><textarea id="prep-answer" rows="4" placeholder="Answer with a concrete example, technical reasoning, and validation steps."></textarea><button class="dark-button" id="prep-submit" type="button">Evaluate my answer <span>↗</span></button><p class="prep-feedback" id="prep-feedback" hidden></p></div>`;
  detail.querySelectorAll("[data-opportunity-status]").forEach((button) => button.addEventListener("click", () => updateOpportunityStatus(job.id, button.dataset.opportunityStatus)));
  detail.querySelector("#prep-submit")?.addEventListener("click", () => submitPreparation(job.id, prep.technical_questions[0]));
}

async function selectOpportunity(jobId) {
  try {
    const data = await apiRequest("/api/opportunities/select", { method: "POST", body: JSON.stringify({ job_id: jobId }) });
    state.opportunities = data;
    renderOpportunities(data);
  } catch {
    showToast("This opportunity could not be selected.");
  }
}

async function updateOpportunityStatus(jobId, status) {
  try {
    const data = await apiRequest("/api/opportunities/status", { method: "POST", body: JSON.stringify({ job_id: jobId, status }) });
    state.opportunities = data;
    renderOpportunities(data);
    showToast(status === "applied" ? "Application progress saved." : "Opportunity saved for preparation.");
  } catch {
    showToast("The opportunity status could not be saved.");
  }
}

async function submitPreparation(jobId, prompt) {
  const answer = document.querySelector("#prep-answer")?.value.trim() || "";
  if (answer.length < 20) {
    showToast("Write at least 20 characters so the coach can evaluate your answer.");
    return;
  }
  try {
    const result = await apiRequest("/api/opportunities/answer", { method: "POST", body: JSON.stringify({ job_id: jobId, prompt, answer }) });
    const feedback = document.querySelector("#prep-feedback");
    if (feedback) {
      feedback.hidden = false;
      feedback.textContent = `${result.result.score}/100 · ${result.result.feedback}`;
    }
    state.opportunities = result.dashboard;
    showToast(`Preparation response evaluated · ${result.result.score}/100.`);
  } catch {
    showToast("The coach could not evaluate that response.");
  }
}

async function syncDashboard() {
  try {
    const data = await apiRequest("/api/dashboard");
    state.backendOnline = true;
    applyDashboard(data);
  } catch {
    state.backendOnline = false;
  }
}

document.querySelectorAll(".filter").forEach((filter) => {
  filter.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    filter.classList.add("active");
    const selectedDomain = filter.dataset.filter || "all";
    document.querySelectorAll(".radar-card").forEach((card) => {
      const domains = (card.dataset.domains || "all").split(" ");
      const visible = selectedDomain === "all" || domains.includes(selectedDomain);
      card.classList.toggle("is-hidden", !visible);
      card.setAttribute("aria-hidden", String(!visible));
    });
    showToast(`${filter.textContent} signals are now in view.`);
  });
});

document.querySelectorAll(".radar-card").forEach((card) => {
  card.addEventListener("click", (event) => {
    if (event.target.closest("a")) return;
    const sourceLink = card.querySelector(".radar-source-link");
    if (sourceLink?.href && sourceLink.getAttribute("href") !== "#") window.open(sourceLink.href, "_blank", "noopener,noreferrer");
  });
});

runButton.addEventListener("click", async () => {
  if (state.running) return;
  state.running = true;
  runButton.innerHTML = '<span class="button-pulse"></span> Scanning sources…';
  runButton.disabled = true;
  showToast("Daily scan started · checking sources and role signals.");
  try {
    const result = await apiRequest("/api/scan", { method: "POST", body: JSON.stringify({ lanes: ["general_ai_development", "sre_devops_support"] }) });
    state.backendOnline = true;
    applyDashboard(result.dashboard);
    runButton.innerHTML = '<span class="button-pulse"></span> Run daily scan <span class="button-arrow">↗</span>';
    runButton.disabled = false;
    state.running = false;
    showToast(`Scan complete · ${result.run.fetched} new source signals added.`);
  } catch {
    state.backendOnline = false;
    window.setTimeout(() => {
      runButton.innerHTML = '<span class="button-pulse"></span> Run daily scan <span class="button-arrow">↗</span>';
      runButton.disabled = false;
      state.running = false;
      showToast("Scan preview complete · backend connection is not available.");
    }, 1200);
    return;
  }
});

document.querySelector("#opportunity-scan")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  button.innerHTML = '<span class="button-pulse"></span> Scanning postings…';
  try {
    const result = await apiRequest("/api/opportunities/scan", { method: "POST", body: JSON.stringify({}) });
    state.opportunities = result.dashboard;
    renderOpportunities(result.dashboard);
    showToast(`Opportunity scan complete · ${result.run.fetched} new postings.`);
  } catch {
    showToast("Opportunity scan failed. Check your configured public feeds.");
  } finally {
    button.disabled = false;
    button.innerHTML = '<span class="button-pulse"></span> Scan opportunities <span class="button-arrow">↗</span>';
  }
});

document.querySelector("#learning-challenge-button")?.addEventListener("click", async () => {
  try {
    const learning = await apiRequest("/api/learning");
    state.backendOnline = true;
    showLearningChallenge(learning);
  } catch {
    showToast("The daily challenge is unavailable until the backend is connected.");
  }
});

document.querySelectorAll("[data-close-challenge]").forEach((element) => {
  element.addEventListener("click", () => { document.querySelector("#challenge-modal").hidden = true; });
});

document.querySelector("#quiz-previous")?.addEventListener("click", () => {
  if (!state.quiz || state.quiz.index === 0) return;
  state.quiz.index -= 1;
  renderQuizQuestion();
  document.querySelector("#challenge-options input")?.focus();
});

document.querySelector("#complete-learning")?.addEventListener("click", async (event) => {
  if (!state.quiz || state.learning?.completed_today) return;
  if (state.quiz.answers[state.quiz.index] == null) {
    showToast("Choose one answer before continuing.");
    return;
  }
  if (state.quiz.index < state.quiz.questions.length - 1) {
    state.quiz.index += 1;
    renderQuizQuestion();
    document.querySelector("#challenge-options input")?.focus();
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    const result = await apiRequest("/api/learning/complete", { method: "POST", body: JSON.stringify({ article_id: state.learning?.challenge?.source_article_id || null, answers: state.quiz.answers }) });
    applyLearning(result.learning);
    renderQuizQuestion();
    renderQuizReview(result.learning);
    showToast(`Quiz complete · ${result.learning.quiz_score}/100 · ${result.learning.streak_days}-day streak.`);
  } catch (error) {
    button.disabled = false;
    renderQuizQuestion();
    showToast("The challenge could not be saved. Try again.");
  }
});

syncDashboard();
