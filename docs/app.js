const SVG_NS = "http://www.w3.org/2000/svg";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const number = new Intl.NumberFormat("en-US");
const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function svgElement(name, attributes = {}, text = "") {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  if (text) element.textContent = text;
  return element;
}

function tableCell(value, tag = "td") {
  const cell = document.createElement(tag);
  cell.textContent = value;
  return cell;
}

function monthLabel(key, dataThrough) {
  const [year, month] = key.split("-").map(Number);
  const label = new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
  return dataThrough.startsWith(key) ? `${label} MTD` : label;
}

function renderMonths(data) {
  const body = document.getElementById("month-rows");
  body.replaceChildren();
  for (const [key, month] of Object.entries(data.months)) {
    const row = document.createElement("tr");
    const blendedCost = month.youtube_responses
      ? month.youtube_spend / month.youtube_responses
      : null;
    row.append(
      tableCell(monthLabel(key, data.data_through)),
      tableCell(currency.format(month.youtube_spend)),
      tableCell(number.format(month.survey_responses)),
      tableCell(number.format(month.youtube_responses)),
      tableCell(percent.format(month.youtube_share)),
      tableCell(blendedCost === null ? "—" : currency.format(blendedCost)),
    );
    row.children[3].replaceChildren(document.createElement("strong"));
    row.children[3].firstChild.textContent = number.format(month.youtube_responses);
    body.append(row);
  }
}

function renderWeeks(data) {
  const body = document.getElementById("week-rows");
  body.replaceChildren();
  for (const week of data.weeks) {
    const row = document.createElement("tr");
    if (week.is_partial) row.classList.add("partial-row");
    const label = document.createElement("td");
    label.textContent = week.label;
    if (week.is_partial) {
      const badge = document.createElement("span");
      badge.className = "partial-badge";
      badge.textContent = "Partial";
      label.append(badge);
    }
    row.append(
      label,
      tableCell(currency.format(week.youtube_spend)),
      tableCell(number.format(week.survey_responses)),
      tableCell(number.format(week.youtube_responses)),
      tableCell(percent.format(week.youtube_share)),
      tableCell(
        week.cost_per_youtube_response === null
          ? "—"
          : currency.format(week.cost_per_youtube_response),
      ),
    );
    row.children[3].replaceChildren(document.createElement("strong"));
    row.children[3].firstChild.textContent = number.format(week.youtube_responses);
    body.append(row);
  }
}

function renderChart(weeks) {
  const svg = document.getElementById("weekly-chart");
  const preserved = [...svg.querySelectorAll("title, desc")];
  svg.replaceChildren(...preserved);

  const width = 1080;
  const height = 480;
  const margin = { top: 42, right: 72, bottom: 86, left: 82 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const maxSpend = Math.max(...weeks.map((week) => week.youtube_spend), 1) * 1.12;
  const maxResponses = Math.max(...weeks.map((week) => week.youtube_responses), 1) * 1.18;
  const slot = plotWidth / weeks.length;
  const barWidth = Math.min(58, slot * 0.5);

  const grid = svgElement("g", { "aria-hidden": "true" });
  for (let index = 0; index <= 4; index += 1) {
    const ratio = index / 4;
    const y = margin.top + plotHeight - ratio * plotHeight;
    grid.append(
      svgElement("line", {
        x1: margin.left,
        x2: width - margin.right,
        y1: y,
        y2: y,
        stroke: "oklch(84% 0.012 80)",
        "stroke-width": 1,
      }),
      svgElement(
        "text",
        {
          x: margin.left - 14,
          y: y + 4,
          "text-anchor": "end",
          fill: "oklch(48% 0.012 80)",
          "font-size": 12,
        },
        currency.format(maxSpend * ratio),
      ),
      svgElement(
        "text",
        {
          x: width - margin.right + 14,
          y: y + 4,
          "text-anchor": "start",
          fill: "oklch(48% 0.012 80)",
          "font-size": 12,
        },
        Math.round(maxResponses * ratio),
      ),
    );
  }
  svg.append(grid);

  const points = [];
  weeks.forEach((week, index) => {
    const centerX = margin.left + slot * index + slot / 2;
    const spendHeight = (week.youtube_spend / maxSpend) * plotHeight;
    const responseY =
      margin.top + plotHeight - (week.youtube_responses / maxResponses) * plotHeight;
    const group = svgElement("g", {
      tabindex: 0,
      role: "img",
      "aria-label": `${week.label}: ${currency.format(week.youtube_spend)} YouTube spend and ${week.youtube_responses} survey acquisitions${week.is_partial ? ", partial week" : ""}`,
    });
    group.append(
      svgElement(
        "title",
        {},
        `${week.label}${week.is_partial ? " (partial)" : ""}: ${currency.format(week.youtube_spend)} YouTube spend, ${week.youtube_responses} survey acquisitions`,
      ),
    );
    const bar = svgElement("rect", {
      x: centerX - barWidth / 2,
      y: margin.top + plotHeight - spendHeight,
      width: barWidth,
      height: spendHeight,
      fill: "oklch(34% 0.08 250)",
      opacity: week.is_partial ? 0.42 : 0.9,
      stroke: week.is_partial ? "oklch(34% 0.08 250)" : "none",
      "stroke-dasharray": week.is_partial ? "6 5" : "none",
    });
    const xLabel = svgElement(
      "text",
      {
        x: centerX,
        y: height - 48,
        "text-anchor": "middle",
        fill: "oklch(48% 0.012 80)",
        "font-size": 12,
      },
      week.label,
    );
    group.append(bar, xLabel);
    svg.append(group);
    points.push([centerX, responseY, week]);
  });

  const line = points.map(([x, y], index) => `${index ? "L" : "M"} ${x} ${y}`).join(" ");
  svg.append(
    svgElement("path", {
      d: line,
      fill: "none",
      stroke: "oklch(52% 0.17 28)",
      "stroke-width": 5,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    }),
  );
  for (const [x, y, week] of points) {
    svg.append(
      svgElement("circle", {
        cx: x,
        cy: y,
        r: 7,
        fill: "oklch(97% 0.008 90)",
        stroke: "oklch(52% 0.17 28)",
        "stroke-width": 4,
        opacity: week.is_partial ? 0.55 : 1,
      }),
    );
  }
  svg.append(
    svgElement(
      "text",
      {
        x: margin.left,
        y: 22,
        fill: "oklch(34% 0.08 250)",
        "font-size": 12,
        "font-weight": 700,
      },
      "YOUTUBE SPEND",
    ),
    svgElement(
      "text",
      {
        x: width - margin.right,
        y: 22,
        "text-anchor": "end",
        fill: "oklch(52% 0.17 28)",
        "font-size": 12,
        "font-weight": 700,
      },
      "SURVEY ACQUISITIONS",
    ),
  );
}

function renderSummary(data) {
  const june = data.months["2026-06"];
  const july = data.months["2026-07"];
  setText("data-through", `Data through ${data.data_through}`);
  setText("total-youtube", number.format(data.summary.total_youtube_responses));
  setText(
    "survey-window",
    `${number.format(data.summary.total_survey_responses)} total survey responses since Jun 3`,
  );
  setText("june-acquisitions", number.format(june.youtube_responses));
  setText("june-spend", `${currency.format(june.youtube_spend)} YouTube spend`);
  setText("july-acquisitions", number.format(july.youtube_responses));
  setText("july-spend", `${currency.format(july.youtube_spend)} YouTube spend`);

  const peak = data.summary;
  const spendChange =
    (peak.latest_complete_youtube_spend - peak.peak_week_youtube_spend) /
    peak.peak_week_youtube_spend;
  const responseChange =
    (peak.latest_complete_youtube_responses - peak.peak_week_youtube_responses) /
    peak.peak_week_youtube_responses;
  setText(
    "readout-copy",
    `${peak.peak_week} was the strongest complete week: ${currency.format(peak.peak_week_youtube_spend)} in spend and ${peak.peak_week_youtube_responses} survey acquisitions. By ${peak.latest_complete_week}, spend was ${percent.format(Math.abs(spendChange))} lower and survey acquisitions were ${percent.format(Math.abs(responseChange))} lower.`,
  );
  setText(
    "confidence-copy",
    `That is worth following, but ${peak.complete_week_count} complete weeks is still a small sample. We will use the Chad Prather launch to see whether the pattern repeats as spend comes back up.`,
  );
}

async function loadDashboard() {
  try {
    const response = await fetch("data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderSummary(data);
    renderChart(data.weeks);
    renderMonths(data);
    renderWeeks(data);
  } catch (error) {
    console.error("Dashboard data failed to load", error);
    document.getElementById("error-state").hidden = false;
  }
}

loadDashboard();
