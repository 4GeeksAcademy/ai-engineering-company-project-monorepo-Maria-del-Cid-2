import { candidates, vacancies, processes } from "../runtime-ts/data/data.js";
import {
  filterCandidatesBySkills,
  filterCandidatesBySeniority,
  filterCandidatesByAvailability,
  sortCandidatesBySalary,
  sortCandidatesByExperience
} from "../runtime-ts/utils/collections.js";
import {
  findCandidateById,
  findCandidateByEmail,
  binarySearchCandidateBySalary
} from "../runtime-ts/utils/search.js";
import {
  countCandidatesByStatus,
  calculateAverageSalary,
  findTopSkills,
  calculateVacancyFillRate,
  rankCandidatesForVacancy
} from "../runtime-ts/utils/transformations.js";
import {
  validateCandidate,
  validateVacancy,
  isValidEmail
} from "../runtime-ts/utils/validations.js";

const $ = (id) => document.getElementById(id);

function candidateCard(candidate) {
  return `
    <div class="rounded-2xl border border-brand-lightgray p-4">
      <p class="font-bold">${candidate.fullName}</p>
      <p class="text-sm text-gray-600">${candidate.email}</p>
      <p class="mt-2 text-sm">Seniority: <b>${candidate.seniority}</b> · Exp: <b>${candidate.yearsOfExperience}</b> años · Salary: <b>${candidate.expectedSalary}</b></p>
      <p class="mt-1 text-sm">Disponibilidad: <b>${candidate.availability}</b> · Estado: <b>${candidate.status}</b></p>
      <p class="mt-1 text-sm">Skills: ${candidate.skills.join(", ")}</p>
    </div>
  `;
}

function renderCandidateList(containerId, list) {
  const container = $(containerId);
  if (!list.length) {
    container.innerHTML = `<p class="rounded-xl bg-brand-lightgray p-3 text-sm">No hay resultados.</p>`;
    return;
  }

  container.innerHTML = `<div class="grid grid-cols-1 gap-3 md:grid-cols-2">${list.map(candidateCard).join("")}</div>`;
}

function renderCandidateTable(containerId, list) {
  const container = $(containerId);

  container.innerHTML = `
    <table class="min-w-full rounded-xl border border-brand-lightgray text-sm">
      <thead class="bg-brand-lightgray">
        <tr>
          <th class="px-3 py-2 text-left">Nombre</th>
          <th class="px-3 py-2 text-left">Email</th>
          <th class="px-3 py-2 text-left">Experiencia</th>
          <th class="px-3 py-2 text-left">Expected Salary</th>
        </tr>
      </thead>
      <tbody>
        ${list.map(c => `
          <tr class="border-t border-brand-lightgray">
            <td class="px-3 py-2">${c.fullName}</td>
            <td class="px-3 py-2">${c.email}</td>
            <td class="px-3 py-2">${c.yearsOfExperience}</td>
            <td class="px-3 py-2">${c.expectedSalary}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderValidationResult(containerId, result) {
  const container = $(containerId);

  if (result.valid) {
    container.innerHTML = `
      <div class="rounded-xl bg-green-100 p-3 text-sm text-green-800">
        <p class="flex items-center gap-2 font-semibold">
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.2 7.2a1 1 0 01-1.414 0l-3.2-3.2a1 1 0 011.414-1.42l2.493 2.492 6.493-6.492a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
          Válido
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="rounded-xl bg-red-100 p-3 text-sm text-red-800">
      <p class="flex items-center gap-2 font-semibold">
        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
        Inválido
      </p>
      <ul class="mt-2 list-disc pl-5">${result.errors.map(e => `<li>${e}</li>`).join("")}</ul>
    </div>
  `;
}

function initSelects() {
  const senioritySelect = $("senioritySelect");
  const availabilitySelect = $("availabilitySelect");
  const vacancySelect = $("vacancySelect");
  const validationCandidateSelect = $("validationCandidateSelect");
  const validationVacancySelect = $("validationVacancySelect");
  const dataSourceInfo = $("dataSourceInfo");

  const seniorities = [...new Set(candidates.map(c => c.seniority))];
  const availabilities = [...new Set(candidates.map(c => c.availability))];

  senioritySelect.innerHTML = seniorities.map(s => `<option value="${s}">${s}</option>`).join("");
  availabilitySelect.innerHTML = availabilities.map(a => `<option value="${a}">${a}</option>`).join("");
  vacancySelect.innerHTML = vacancies.map(v => `<option value="${v.id}">${v.title} — ${v.companyName}</option>`).join("");

  if (validationCandidateSelect) {
    validationCandidateSelect.innerHTML = candidates
      .map(c => `<option value="${c.id}">${c.fullName}</option>`)
      .join("");
  }

  if (validationVacancySelect) {
    validationVacancySelect.innerHTML = vacancies
      .map(v => `<option value="${v.id}">${v.title} — ${v.companyName}</option>`)
      .join("");
  }

  $("emailValidationInput").value = candidates[0].email;

  if (dataSourceInfo) {
    dataSourceInfo.textContent = `Fuente: src/runtime-ts/data/data.js · Candidatos cargados: ${candidates.length}`;
  }
}

function initHeaderMenu() {
  const btn = document.querySelector("[data-menu-button]");
  const menu = document.querySelector("[data-mobile-menu]");

  if (!btn || !menu) return;

  btn.addEventListener("click", () => {
    const expanded = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!expanded));
    menu.classList.toggle("hidden");
  });
}

function bindEvents() {
  $("runFiltersBtn").addEventListener("click", () => {
    const skillText = $("skillsInput").value.trim();
    const seniority = $("senioritySelect").value;
    const availability = $("availabilitySelect").value;

    let result = [...candidates];

    if (skillText) {
      const requiredSkills = skillText
        .split(",")
        .map(s => s.trim())
        .filter(Boolean);
      result = filterCandidatesBySkills(result, requiredSkills);
    }

    if (seniority) {
      result = filterCandidatesBySeniority(result, seniority);
    }

    if (availability) {
      result = filterCandidatesByAvailability(result, [availability]);
    }

    renderCandidateList("filterResults", result);
  });

  $("searchByIdBtn").addEventListener("click", () => {
    const id = $("searchIdInput").value.trim();
    const found = findCandidateById(candidates, id);
    renderCandidateList("searchResults", found ? [found] : []);
  });

  $("searchByEmailBtn").addEventListener("click", () => {
    const email = $("searchEmailInput").value.trim();
    const found = findCandidateByEmail(candidates, email);
    renderCandidateList("searchResults", found ? [found] : []);
  });

  $("binarySearchBtn").addEventListener("click", () => {
    const value = Number($("binarySalaryInput").value);
    const sorted = sortCandidatesBySalary(candidates, "asc");
    const index = binarySearchCandidateBySalary(sorted, value);

    if (index === -1) {
      $("searchResults").innerHTML = `<p class="rounded-xl bg-brand-lightgray p-3 text-sm">No se encontró candidate con expectedSalary = ${value}.</p>`;
      return;
    }

    renderCandidateList("searchResults", [sorted[index]]);
  });

  $("sortBtn").addEventListener("click", () => {
    const field = $("sortFieldSelect").value;
    const order = $("sortOrderSelect").value;

    const sorted = field === "salary"
      ? sortCandidatesBySalary(candidates, order)
      : sortCandidatesByExperience(candidates, order);

    renderCandidateTable("sortResults", sorted);
  });

  $("loadReportsBtn").addEventListener("click", () => {
    const byStatus = countCandidatesByStatus(candidates);
    const avgSalary = calculateAverageSalary(candidates);
    const topSkills = findTopSkills(candidates, 5);
    const fillRate = calculateVacancyFillRate(processes);

    $("reportsResults").innerHTML = `
      <div class="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div class="rounded-2xl bg-brand-lightgray p-4"><p class="text-sm">Activos</p><p class="text-2xl font-black">${byStatus["Active"]}</p></div>
        <div class="rounded-2xl bg-brand-lightgray p-4"><p class="text-sm">En proceso</p><p class="text-2xl font-black">${byStatus["In process"]}</p></div>
        <div class="rounded-2xl bg-brand-lightgray p-4"><p class="text-sm">Contratados</p><p class="text-2xl font-black">${byStatus["Hired"]}</p></div>
        <div class="rounded-2xl bg-brand-lightgray p-4"><p class="text-sm">Inactivos</p><p class="text-2xl font-black">${byStatus["Inactive"]}</p></div>
      </div>
      <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div class="rounded-2xl border border-brand-lightgray p-4">
          <p class="text-sm">Salario medio esperado</p>
          <p class="text-2xl font-black">${avgSalary}</p>
        </div>
        <div class="rounded-2xl border border-brand-lightgray p-4">
          <p class="text-sm">% vacantes finalizadas con contratación</p>
          <p class="text-2xl font-black">${fillRate}%</p>
        </div>
      </div>
      <div class="mt-4 rounded-2xl border border-brand-lightgray p-4">
        <p class="mb-2 text-sm font-semibold">Habilidades más frecuentes</p>
        <ul class="list-disc pl-5 text-sm">
          ${topSkills.map(s => `<li>${s.skill}: ${s.count}</li>`).join("")}
        </ul>
      </div>
    `;
  });

  $("rankBtn").addEventListener("click", () => {
    const vacancyId = $("vacancySelect").value;
    const vacancy = vacancies.find(v => v.id === vacancyId);

    if (!vacancy) return;

    const ranked = rankCandidatesForVacancy(candidates, vacancy);

    $("rankingResults").innerHTML = `
      <table class="min-w-full rounded-xl border border-brand-lightgray text-sm">
        <thead class="bg-brand-lightgray">
          <tr>
            <th class="px-3 py-2 text-left">Posición</th>
            <th class="px-3 py-2 text-left">Candidato</th>
            <th class="px-3 py-2 text-left">Puntuación</th>
          </tr>
        </thead>
        <tbody>
          ${ranked.map((r, i) => `
            <tr class="border-t border-brand-lightgray">
              <td class="px-3 py-2">${i + 1}</td>
              <td class="px-3 py-2">${r.candidate.fullName}</td>
              <td class="px-3 py-2">${r.score}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  });

  $("validateCandidateBtn").addEventListener("click", () => {
    const selectedId = $("validationCandidateSelect").value;
    const selectedCandidate = candidates.find(candidate => candidate.id === selectedId);

    if (!selectedCandidate) {
      $("candidateValidationResult").innerHTML = `<p class="rounded-xl bg-red-100 p-3 text-sm text-red-800">Selecciona un candidato válido.</p>`;
      return;
    }

    renderValidationResult("candidateValidationResult", validateCandidate(selectedCandidate));
  });

  $("validateVacancyBtn").addEventListener("click", () => {
    const selectedId = $("validationVacancySelect").value;
    const selectedVacancy = vacancies.find(vacancy => vacancy.id === selectedId);

    if (!selectedVacancy) {
      $("vacancyValidationResult").innerHTML = `<p class="rounded-xl bg-red-100 p-3 text-sm text-red-800">Selecciona una vacante válida.</p>`;
      return;
    }

    renderValidationResult("vacancyValidationResult", validateVacancy(selectedVacancy));
  });

  $("validateEmailBtn").addEventListener("click", () => {
    const email = $("emailValidationInput").value.trim();
    const ok = isValidEmail(email);

    $("emailValidationResult").innerHTML = ok
      ? `<p class="rounded-xl bg-green-100 p-3 text-sm text-green-800">Email válido ✅</p>`
      : `<p class="rounded-xl bg-red-100 p-3 text-sm text-red-800">Email inválido ❌</p>`;
  });
}

initHeaderMenu();
initSelects();
bindEvents();
