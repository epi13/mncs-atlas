const toggle = document.querySelector('.nav-toggle');
const nav = document.querySelector('#site-nav');

function closeNav() {
  if (!toggle || !nav) return;
  nav.classList.remove('open');
  toggle.setAttribute('aria-expanded', 'false');
}

if (toggle && nav) {
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });

  nav.addEventListener('click', (event) => {
    if (event.target instanceof HTMLAnchorElement) closeNav();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && nav.classList.contains('open')) {
      closeNav();
      toggle.focus();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 820) closeNav();
  });
}

const year = document.querySelector('#year');
if (year) year.textContent = String(new Date().getFullYear());

function humanize(value) {
  return String(value || '')
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function maturityClass(value) {
  if (value === 'active-infrastructure') return 'active';
  if (value === 'experimental') return 'experimental';
  if (value === 'orientation') return 'orientation';
  return 'research';
}

function repoName(url) {
  try {
    const path = new URL(url).pathname.split('/').filter(Boolean);
    return path[path.length - 1] || url;
  } catch {
    return url;
  }
}

function buildProjectCard(project, relationships) {
  const card = document.createElement('a');
  card.className = 'project-card';
  card.href = project.repository;

  const type = document.createElement('span');
  type.className = 'project-type';
  type.textContent = humanize(project.role);

  const title = document.createElement('h3');
  title.textContent = project.name;

  const body = document.createElement('p');
  body.textContent = project.responsibility;

  const relationCount = relationships.filter((relation) => relation.from === project.id || relation.to === project.id).length;
  const footer = document.createElement('span');
  footer.className = 'repo-link';
  footer.textContent = `${repoName(project.repository)} · ${humanize(project.maturity)} · ${relationCount} mapped relation${relationCount === 1 ? '' : 's'} ↗`;

  card.append(type, title, body, footer);
  return card;
}

function buildStatusCard(project) {
  const card = document.createElement('article');
  card.className = 'status-card';

  const badge = document.createElement('span');
  badge.className = `status-badge ${maturityClass(project.maturity)}`;
  badge.textContent = humanize(project.maturity);

  const title = document.createElement('h3');
  title.textContent = project.name;

  const body = document.createElement('p');
  body.textContent = `${humanize(project.authority_class)}. ${project.responsibility}`;

  card.append(badge, title, body);
  return card;
}

function renderMaturityModel(atlas) {
  const status = document.querySelector('#status .shell');
  if (!status || !atlas.maturity_model?.levels || status.querySelector('[data-atlas-maturity-model]')) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'runtime-notes';
  wrapper.dataset.atlasMaturityModel = 'true';

  Object.entries(atlas.maturity_model.levels).forEach(([id, level]) => {
    const article = document.createElement('article');
    const kicker = document.createElement('p');
    kicker.className = 'card-kicker';
    kicker.textContent = humanize(id);
    const title = document.createElement('h3');
    title.textContent = level.meaning;
    const body = document.createElement('p');
    body.textContent = level.dependency_policy;
    article.append(kicker, title, body);
    wrapper.append(article);
  });

  status.append(wrapper);
}

function renderConsumerContract(atlas) {
  const contribute = document.querySelector('#contribute .callout');
  if (!contribute || !atlas.consumer_contract || document.querySelector('[data-atlas-consumer-contract]')) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'shell runtime-notes';
  wrapper.dataset.atlasConsumerContract = 'true';

  const order = document.createElement('article');
  const orderKicker = document.createElement('p');
  orderKicker.className = 'card-kicker';
  orderKicker.textContent = 'Machine consumer contract';
  const orderTitle = document.createElement('h3');
  orderTitle.textContent = `Atlas ${atlas.schema_version} · reviewed ${atlas.last_reviewed}`;
  const orderBody = document.createElement('p');
  orderBody.textContent = atlas.consumer_contract.resolution_order.join(' → ');
  order.append(orderKicker, orderTitle, orderBody);

  const rules = document.createElement('article');
  const rulesKicker = document.createElement('p');
  rulesKicker.className = 'card-kicker';
  rulesKicker.textContent = 'Consumption rules';
  const rulesTitle = document.createElement('h3');
  rulesTitle.textContent = 'Orientation remains evidence-bounded.';
  const rulesBody = document.createElement('p');
  rulesBody.textContent = atlas.consumer_contract.rules.join(' ');
  rules.append(rulesKicker, rulesTitle, rulesBody);

  const topology = document.createElement('article');
  const topologyKicker = document.createElement('p');
  topologyKicker.className = 'card-kicker';
  topologyKicker.textContent = 'Current family state';
  const topologyTitle = document.createElement('h3');
  topologyTitle.textContent = `${atlas.projects.length} projects · ${atlas.operator_components.length} operator components · ${atlas.relationships.length} explicit relationships`;
  const topologyBody = document.createElement('p');
  topologyBody.textContent = 'The page renders project and maturity views from atlas.json so human orientation and machine discovery share one canonical family record.';
  topology.append(topologyKicker, topologyTitle, topologyBody);

  wrapper.append(order, rules, topology);
  contribute.parentNode.insertBefore(wrapper, contribute);
}

function renderInstitutionalLayer(atlas) {
  const map = document.querySelector('.architecture-map');
  const authority = map?.querySelector('.arch-layer.authority');
  if (!map || !authority || map.querySelector('[data-atlas-layer="institutional"]')) return;

  const rights = atlas.projects.find((project) => project.id === 'rights-provenance');
  const orientation = atlas.projects.find((project) => project.id === 'atlas');
  if (!rights) return;

  const existingArrow = authority.nextElementSibling;
  const layer = document.createElement('div');
  layer.className = 'arch-layer';
  layer.dataset.atlasLayer = 'institutional';

  const label = document.createElement('span');
  label.className = 'layer-label';
  label.textContent = 'Incubating / institutional';

  const rightsCard = document.createElement('div');
  rightsCard.className = 'arch-card featured';
  const rightsName = document.createElement('strong');
  rightsName.textContent = rights.name;
  const rightsDetail = document.createElement('small');
  rightsDetail.textContent = 'origin · lineage · rights basis · authorship uncertainty · artifact licensing';
  rightsCard.append(rightsName, rightsDetail);

  layer.append(label, rightsCard);

  if (orientation) {
    const atlasCard = document.createElement('div');
    atlasCard.className = 'arch-card';
    const atlasName = document.createElement('strong');
    atlasName.textContent = orientation.name;
    const atlasDetail = document.createElement('small');
    atlasDetail.textContent = 'family orientation · machine discovery · no conformance authority';
    atlasCard.append(atlasName, atlasDetail);
    layer.append(atlasCard);
  }

  const arrow = document.createElement('div');
  arrow.className = 'flow-arrow';
  arrow.setAttribute('aria-hidden', 'true');
  arrow.textContent = '↓';

  if (existingArrow) {
    existingArrow.insertAdjacentElement('afterend', layer);
    layer.insertAdjacentElement('afterend', arrow);
  }
}

async function enhanceFromAtlas() {
  try {
    const response = await fetch('atlas.json', { cache: 'no-cache' });
    if (!response.ok) return;
    const atlas = await response.json();

    const projectGrid = document.querySelector('#projects .project-grid');
    if (projectGrid && Array.isArray(atlas.projects) && Array.isArray(atlas.relationships)) {
      projectGrid.replaceChildren(...atlas.projects.map((project) => buildProjectCard(project, atlas.relationships)));
    }

    const statusGrid = document.querySelector('#status .status-grid');
    if (statusGrid && Array.isArray(atlas.projects)) {
      statusGrid.replaceChildren(...atlas.projects.map(buildStatusCard));
    }

    renderInstitutionalLayer(atlas);
    renderMaturityModel(atlas);
    renderConsumerContract(atlas);
  } catch {
    // Static HTML remains a complete fallback if machine orientation cannot be loaded.
  }
}

enhanceFromAtlas();
