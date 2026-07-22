const SVG_NS = "http://www.w3.org/2000/svg";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const decimalCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const number = new Intl.NumberFormat("en-US");

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function element(name, className = "", text = "") {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function svgElement(name, attributes = {}, text = "") {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    node.setAttribute(key, String(value));
  }
  if (text) node.textContent = text;
  return node;
}

function renderSummary(data) {
  const summary = data.summary;
  const dataThrough = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${data.data_through}T00:00:00Z`));
  setText("report-window", data.reporting_window.label);
  setText("data-through", `Data through ${dataThrough}`);
  setText("youtube-spend", currency.format(summary.youtube_spend));
  setText("youtube-acquisitions", number.format(summary.youtube_responses));
  setText("youtube-revenue", currency.format(summary.youtube_revenue));
  setText("survey-roas", `${summary.survey_attributed_roas.toFixed(2)}x`);
  setText("youtube-aov", currency.format(summary.youtube_aov));
  setText(
    "aov-comparison",
    `All surveyed orders ${currency.format(summary.all_survey_aov)}`,
  );
  setText(
    "cost-per-acquisition",
    currency.format(summary.cost_per_youtube_response),
  );
  setText(
    "match-rate",
    `${summary.matched_youtube_orders}/${summary.youtube_responses} survey orders matched to Shopify`,
  );
}

function renderChart(weeks) {
  const svg = document.getElementById("weekly-chart");
  const preserved = [...svg.querySelectorAll("title, desc")];
  svg.replaceChildren(...preserved);

  const width = 1080;
  const height = 390;
  const margin = { top: 38, right: 58, bottom: 66, left: 68 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const maxSpend = Math.max(...weeks.map((week) => week.youtube_spend), 1) * 1.16;
  const maxResponses = Math.max(...weeks.map((week) => week.youtube_responses), 1) * 1.2;
  const slot = plotWidth / weeks.length;
  const barWidth = Math.min(76, slot * 0.48);

  for (let index = 0; index <= 3; index += 1) {
    const ratio = index / 3;
    const y = margin.top + plotHeight - ratio * plotHeight;
    svg.append(
      svgElement("line", {
        x1: margin.left,
        x2: width - margin.right,
        y1: y,
        y2: y,
        class: "grid-line",
      }),
      svgElement(
        "text",
        { x: margin.left - 12, y: y + 4, "text-anchor": "end", class: "axis-label" },
        currency.format(maxSpend * ratio),
      ),
      svgElement(
        "text",
        { x: width - margin.right + 12, y: y + 4, class: "axis-label" },
        Math.round(maxResponses * ratio),
      ),
    );
  }

  const points = [];
  weeks.forEach((week, index) => {
    const centerX = margin.left + slot * index + slot / 2;
    const spendHeight = (week.youtube_spend / maxSpend) * plotHeight;
    const responseY =
      margin.top + plotHeight - (week.youtube_responses / maxResponses) * plotHeight;
    const group = svgElement("g", {
      tabindex: 0,
      role: "img",
      "aria-label": `${week.label}: ${currency.format(week.youtube_spend)} spend, ${week.youtube_responses} survey acquisitions, ${decimalCurrency.format(week.youtube_revenue)} matched revenue`,
    });
    group.append(
      svgElement(
        "title",
        {},
        `${week.label}: ${currency.format(week.youtube_spend)} spend, ${week.youtube_responses} survey acquisitions, ${currency.format(week.youtube_revenue)} revenue`,
      ),
      svgElement("rect", {
        x: centerX - barWidth / 2,
        y: margin.top + plotHeight - spendHeight,
        width: barWidth,
        height: spendHeight,
        class: "spend-bar",
        rx: 3,
      }),
      svgElement(
        "text",
        {
          x: centerX,
          y: margin.top + plotHeight - spendHeight - 10,
          "text-anchor": "middle",
          class: "bar-value",
        },
        currency.format(week.youtube_spend),
      ),
      svgElement(
        "text",
        {
          x: centerX,
          y: height - 28,
          "text-anchor": "middle",
          class: "week-label",
        },
        week.label.replace("–", "–\n"),
      ),
    );
    svg.append(group);
    points.push([centerX, responseY, week]);
  });

  const line = points
    .map(([x, y], index) => `${index ? "L" : "M"} ${x} ${y}`)
    .join(" ");
  svg.append(
    svgElement("path", {
      d: line,
      class: "survey-line",
    }),
  );
  for (const [x, y, week] of points) {
    svg.append(
      svgElement("circle", { cx: x, cy: y, r: 7, class: "survey-point" }),
      svgElement(
        "text",
        { x, y: y - 14, "text-anchor": "middle", class: "survey-value" },
        week.youtube_responses,
      ),
    );
  }
}

function videoPlayer(video) {
  const card = element("article", "video-card");
  const trigger = element("button", "video-trigger");
  trigger.type = "button";
  trigger.setAttribute("aria-label", `Play ${video.title}`);

  const image = document.createElement("img");
  image.src = `https://i.ytimg.com/vi/${video.youtube_id}/hqdefault.jpg`;
  image.alt = "";
  image.loading = "eager";
  image.decoding = "async";
  image.referrerPolicy = "no-referrer";
  trigger.append(image, element("span", "play", "▶"));
  trigger.addEventListener("click", () => {
    const frame = document.createElement("iframe");
    frame.className = "video-frame";
    frame.src = `https://www.youtube-nocookie.com/embed/${video.youtube_id}?autoplay=1`;
    frame.title = video.title;
    frame.loading = "lazy";
    frame.allow = "autoplay; encrypted-media; picture-in-picture";
    frame.allowFullscreen = true;
    trigger.replaceWith(frame);
  });

  const info = element("div", "video-info");
  const title = element("strong", "", video.title);
  const meta = element("div", "video-meta");
  const spend = element("span", "", `${currency.format(video.spend)} spend`);
  const link = element("a", "", "Open on YouTube");
  link.href = `https://www.youtube.com/watch?v=${video.youtube_id}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  meta.append(spend, link);
  info.append(title, meta);
  card.append(trigger, info);
  return card;
}

function renderFeaturedVideos(months) {
  const container = document.getElementById("featured-video-months");
  container.replaceChildren();
  for (const month of months) {
    const section = element("section", "video-month");
    const heading = element("div", "month-heading");
    heading.append(
      element("h3", "", month.label),
      element("span", "", `${month.videos.length} videos`),
    );
    const gallery = element("div", "video-grid featured-grid");
    month.videos.forEach((video) => gallery.append(videoPlayer(video)));
    section.append(heading, gallery);
    container.append(section);
  }
}

function renderCreators(creators) {
  const list = document.getElementById("creator-list");
  list.replaceChildren();
  for (const creator of creators) {
    const details = element("details", "creator");
    const summary = document.createElement("summary");
    summary.append(
      element("strong", "creator-name", creator.creator),
      element("span", "", currency.format(creator.spend)),
      element("span", "", currency.format(creator.google_reported_revenue)),
      element("span", "", `${creator.google_reported_roas.toFixed(2)}x`),
      element("span", "video-count", `${creator.video_count} ▾`),
    );
    const gallery = element("div", "video-grid");
    creator.videos.forEach((video) => gallery.append(videoPlayer(video)));
    details.append(summary, gallery);
    list.append(details);
  }
}

async function loadDashboard() {
  try {
    const response = await fetch("data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderSummary(data);
    renderChart(data.weeks);
    renderFeaturedVideos(data.featured_videos_by_month);
    renderCreators(data.june_creators);
  } catch (error) {
    console.error("Dashboard data failed to load", error);
    document.getElementById("error-state").hidden = false;
  }
}

loadDashboard();
