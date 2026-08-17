// Para ejecutar las pruebas: npx tsx src/utils/demo.ts


import { filterCandidatesBySkills,  filterCandidatesBySeniority,  filterCandidatesByAvailability, sortCandidatesBySalary, sortCandidatesByExperience } from "../utils/collections";
import { Candidate, CandidateStatus, SelectionProcess } from "../types/models";
import { findCandidateById, findCandidateByEmail, binarySearchCandidateBySalary} from "../utils/search";
import { countCandidatesByStatus, calculateAverageSalary, findTopSkills, calculateVacancyFillRate, calculateCandidateScore, rankCandidatesForVacancy,groupCandidatesBySeniority } from "../utils/transformations";
import { validateCandidate, validateVacancy, isValidEmail } from "../utils/validations";
import { candidates, vacancies, processes } from "../data/data";



const result = filterCandidatesBySkills(candidates, ["TypeScript"]);
console.log(result);

const seniorCandidates = filterCandidatesBySeniority(candidates, "Senior");
console.log(seniorCandidates);

const availableCandidates = filterCandidatesByAvailability(
    candidates,
    ["Immediate", "2 weeks"]
);
console.log(availableCandidates);

const salaryAsc = sortCandidatesBySalary(candidates, "asc");
console.log("Salario ascendente:", salaryAsc);

const salaryDesc = sortCandidatesBySalary(candidates, "desc");
console.log("Salario descendente:", salaryDesc);

const experienceAsc = sortCandidatesByExperience(candidates, "asc");
console.log("Experiencia ascendente:", experienceAsc);

const experienceDesc = sortCandidatesByExperience(candidates, "desc");
console.log("Experiencia descendente:", experienceDesc);

console.log("Buscar por ID:");
console.log(findCandidateById(candidates, "1"));
console.log(findCandidateById(candidates, "999"));


console.log("Buscar por email:");
console.log(findCandidateByEmail(candidates, "ANA@EMAIL.COM"));
console.log(findCandidateByEmail(candidates, "noexiste@email.com"));

const candidatesBySalary = sortCandidatesBySalary(candidates, "asc");

console.log("Búsqueda binaria:");
console.log(binarySearchCandidateBySalary(candidatesBySalary, 35000));
console.log(binarySearchCandidateBySalary(candidatesBySalary, 50000));

console.log("Candidatos por estado:");
console.log(countCandidatesByStatus(candidates));

console.log("Salario medio:");
console.log(calculateAverageSalary(candidates));

console.log("Habilidades más frecuentes:");
console.log(findTopSkills(candidates, 3));

console.log("Porcentaje de procesos contratados:");
console.log(calculateVacancyFillRate(processes));

console.log("Validación del candidato:");
console.log(validateCandidate(candidates[0]));

console.log("Validación del email:");
console.log(isValidEmail(candidates[0].email));

console.log("Validación de la primera vacante:");
console.log(validateVacancy(vacancies[0]));

console.log("Validación de la segunda vacante:");
console.log(validateVacancy(vacancies[1]));

console.log("Puntuación de Ana para la vacante:");
console.log(calculateCandidateScore(candidates[0], vacancies[0]));

console.log("Ranking de candidatos para la vacante:");
console.log(rankCandidatesForVacancy(candidates, vacancies[0]));

console.log("Candidatos agrupados por seniority:");
console.log(groupCandidatesBySeniority(candidates));