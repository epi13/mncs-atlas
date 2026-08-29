import { runAtlasWasm } from "./atlas-wasm.js";

const atlasBaseUrl = new URL("../", import.meta.url);
const atlasUrl = (path = "") => new URL(path, atlasBaseUrl).toString();

const toggle = document.querySelector(".nav-toggle");
const nav = document.querySelector("#site-nav");

function closeNav() {
  if (!toggle || !nav) return;
  nav.classList.remove("open");
  toggle.setAttribute("aria-expanded", "false");
}

if (toggle && nav) {
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });

  nav.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) closeNav();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("open")) {
      closeNav();
      toggle.focus();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) closeNav();
  });
}

const year = document.querySelector("#year");
if (year) year.textContent = String(new Date().getFullYear());

function ensureJournalNavigation() {
  if (!nav) return;
  const alreadyLinked = [...nav.querySelectorAll("a")].some((link) => link.textContent.trim() === "Journal");
  if (alreadyLinked) return;

  const link = document.createElement("a");
  link.href = atlasUrl("journal/");
  link.textContent = "Journal";

  const contribute = [...nav.querySelectorAll("a")].find((candidate) =>
    candidate.getAttribute("href")?.includes("contribute"));
  if (contribute) nav.insertBefore(link, contribute);
  else nav.append(link);
}

function ensureJournalFooter() {
  const footerLinks = document.querySelector(".footer-links");
  if (!footerLinks) return;
  const alreadyLinked = [...footerLinks.querySelectorAll("a")].some((link) => link.textContent.trim() === "Journal");
  if (alreadyLinked) return;

  const link = document.createElement("a");
  link.href = atlasUrl("journal/");
  link.textContent = "Journal";
  footerLinks.append(link);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function renderJournalEntryPoint() {
  const contribute = document.querySelector("#contribute");
  if (!contribute || document.querySelector("#journal")) return;

  const section = element("section", "section section-dark");
  section.id = "journal";
  const shell = element("div", "shell two-col");
  const copy = element("div");
  copy.append(
    element("p", "eyebrow", "Development Journal"),
    element("h2", "The reasoning, experiments, wrong turns, and architectural shifts behind MNCS.")
  );
  const prose = element("div", "prose");
  prose.append(
    element("p", "Atlas explains where the MNCS project family stands. The Development Journal records how it gets there: decisions while they are still fresh, experiments that change the design, failures worth remembering, and ideas that may later become formal work."),
    element("p", "Journal entries are dated snapshots and are deliberately non-normative. Current specifications and owning-repository documentation remain authoritative.")
  );
  const link = element("a", "button primary", "Read the Development Journal");
  link.href = atlasUrl("journal/");
  prose.append(link);
  shell.append(copy, prose);
  section.append(shell);
  contribute.insertAdjacentElement("beforebegin", section);
}

function bootAtlasPage() {
  ensureJournalNavigation();
  ensureJournalFooter();
  renderJournalEntryPoint();
  void runAtlasWasm();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootAtlasPage, { once: true });
} else {
  bootAtlasPage();
}
