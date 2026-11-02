const state = { currentView: "overview", running: false, selectedArticle: 0 };
const panels = [...document.querySelectorAll("[data-panel]")];
const navItems = [...document.querySelectorAll("[data-view]")];
const breadcrumb = document.querySelector("#breadcrumb-current");
const pageTitle = document.querySelector("#page-title");
const toast = document.querySelector("#toast");
const runButton = document.querySelector("#run-button");

const titles = {
  overview: { breadcrumb: "Overview", title: "Your technical edge,<br /><em>one day sharper.</em>" },
  workflow: { breadcrumb: "Agent workflow", title: "See the loop,<br /><em>step by step.</em>" },
  radar: { breadcrumb: "Technical radar", title: "Signals worth<br /><em>your attention.</em>" },
  lab: { breadcrumb: "Career lab", title: "Practice the work,<br /><em>earn the edge.</em>" },
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 3600);
}

function setView(view) {
  state.currentView = view;
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  panels.forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === view));
  breadcrumb.textContent = titles[view].breadcrumb;
  pageTitle.innerHTML = titles[view].title;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll("[data-view-target]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});
navItems.forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));

document.querySelectorAll(".agent-card").forEach((agent) => {
  agent.addEventListener("click", () => {
    if (agent.dataset.agent === "coach") {
      showToast("NextLevelPersonalCoachForCareerLevel is queued for phase two.");
      return;
    }
    showToast("DailyTechUpgradeAgent is already your active coworker.");
  });
});

document.querySelectorAll(".article-row").forEach((article) => {
  article.addEventListener("click", () => {
    state.selectedArticle = Number(article.dataset.article);
    document.querySelectorAll(".article-row").forEach((row) => row.classList.remove("selected"));
    article.classList.add("selected");
    const source = article.querySelector(".article-footer span")?.textContent || "source";
    showToast(`Brief selected · ${source}`);
  });
});

document.querySelectorAll(".filter").forEach((filter) => {
  filter.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    filter.classList.add("active");
    showToast(`${filter.textContent} signals are now in view.`);
  });
});

runButton.addEventListener("click", () => {
  if (state.running) return;
  state.running = true;
  runButton.innerHTML = '<span class="button-pulse"></span> Scanning sources…';
  runButton.disabled = true;
  showToast("Daily scan started · checking sources and role signals.");
  window.setTimeout(() => {
    runButton.innerHTML = '<span class="button-pulse"></span> Run daily scan <span class="button-arrow">↗</span>';
    runButton.disabled = false;
    state.running = false;
    showToast("Scan complete · 2 new signals added to your brief.");
  }, 2400);
});

document.querySelector("#challenge-button")?.addEventListener("click", () => {
  setView("lab");
  showToast("Challenge ready · answer the incident command prompt.");
});

document.querySelector("#submit-answer")?.addEventListener("click", (event) => {
  const answer = document.querySelector(".answer-box").textContent.trim();
  if (!answer || answer === "Start typing your response…") {
    showToast("Add a response first so the agent can evaluate your thinking.");
    document.querySelector(".answer-box").focus();
    return;
  }
  const submitButton = event.currentTarget;
  submitButton.innerHTML = "Evaluating…";
  submitButton.disabled = true;
  window.setTimeout(() => {
    submitButton.innerHTML = 'Feedback ready <span>↗</span>';
    showToast("Assessment complete · your readiness report has been updated.");
  }, 1400);
});

document.querySelector(".answer-box")?.addEventListener("focus", (event) => {
  const placeholder = event.currentTarget.querySelector("span");
  if (placeholder) placeholder.remove();
});
