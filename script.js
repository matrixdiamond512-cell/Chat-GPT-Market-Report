const latestReport = document.getElementById("latestReport");
const reportGrid = document.getElementById("reportGrid");
const timeFilter = document.getElementById("timeFilter");
const searchInput = document.getElementById("searchInput");
const resultCount = document.getElementById("resultCount");
const emptyMessage = document.getElementById("emptyMessage");
const dialog = document.getElementById("imageDialog");
const dialogImage = document.getElementById("dialogImage");
const dialogCaption = document.getElementById("dialogCaption");
const closeDialog = document.getElementById("closeDialog");

let reports = [];

function formatDateTime(item) {
  return `${item.date.replaceAll("-", "/")} ${item.time}`;
}

function openImage(item) {
  dialogImage.src = item.image;
  dialogImage.alt = item.title;
  dialogCaption.textContent = `${item.title}｜${formatDateTime(item)}`;
  dialog.showModal();
}

function card(item, latest = false) {
  const article = document.createElement("article");
  article.className = latest ? "latest-card" : "report-card";

  const button = document.createElement("button");
  button.type = "button";
  button.addEventListener("click", () => openImage(item));

  const img = document.createElement("img");
  img.src = item.image;
  img.alt = item.title;
  img.loading = latest ? "eager" : "lazy";

  const body = document.createElement("div");
  body.className = "card-body";

  const title = document.createElement("h3");
  title.textContent = item.title;

  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = `${formatDateTime(item)}${item.tags?.length ? "｜" + item.tags.join("・") : ""}`;

  body.append(title, meta);
  button.append(img, body);
  article.append(button);
  return article;
}

function render() {
  const selectedTime = timeFilter.value;
  const keyword = searchInput.value.trim().toLowerCase();

  const filtered = reports.filter(item => {
    const timeMatch = selectedTime === "all" || item.time === selectedTime;
    const haystack = [item.title, item.date, item.time, ...(item.tags || [])].join(" ").toLowerCase();
    return timeMatch && (!keyword || haystack.includes(keyword));
  });

  reportGrid.innerHTML = "";
  filtered.forEach(item => reportGrid.append(card(item)));

  resultCount.textContent = `${filtered.length}件`;
  emptyMessage.hidden = filtered.length !== 0;
}

async function init() {
  try {
    const response = await fetch("reports.json", { cache: "no-store" });
    if (!response.ok) throw new Error("reports.jsonを取得できませんでした。");
    reports = await response.json();
    reports.sort((a, b) => (`${b.date} ${b.time}`).localeCompare(`${a.date} ${a.time}`));

    latestReport.innerHTML = "";
    if (reports[0]) latestReport.append(card(reports[0], true));
    render();
  } catch (error) {
    latestReport.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

timeFilter.addEventListener("change", render);
searchInput.addEventListener("input", render);
closeDialog.addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => {
  if (event.target === dialog) dialog.close();
});

init();
