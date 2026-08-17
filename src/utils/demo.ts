import { filterCandidatesBySkills,  filterCandidatesBySeniority,  filterCandidatesByAvailability, sortCandidatesBySalary, sortCandidatesByExperience } from "./collections";
import { Candidate, CandidateStatus, SelectionProcess } from "../types/models";
import { findCandidateById, findCandidateByEmail, binarySearchCandidateBySalary} from "./search";
import { countCandidatesByStatus, calculateAverageSalary, findTopSkills, calculateVacancyFillRate, calculateCandidateScore, rankCandidatesForVacancy,groupCandidatesBySeniority } from "./transformations";
import { validateCandidate, validateVacancy, isValidEmail } from "./validations";


const candidates: Candidate[] = [
    {
        id: "1",
        fullName: "Ana García",
        email: "ana@email.com",
        phone: "600123456",
        yearsOfExperience: 5,
        skills: ["JavaScript", "TypeScript", "React"],
        englishLevel: "C1",
        seniority: "Senior",
        currentSalary: 30000,
        expectedSalary: 35000,
        availability: "Immediate",
        location: "Madrid",
        remoteOnly: true,
        status: "Active"
    },
    {
        id: "2",
        fullName: "Carlos López",
        email: "carlos@email.com",
        phone: "600654321",
        yearsOfExperience: 2,
        skills: ["Python", "Java"],
        englishLevel: "B2",
        seniority: "Junior",
        currentSalary: 25000,
        expectedSalary: 28000,
        availability: "2 weeks",
        location: "Valencia",
        remoteOnly: false,
        status: "Active"
    }
];

const processes: SelectionProcess[] = [
    {
        id: "1",
        candidateId: "1",
        vacancyId: "1",
        stage: "Hired",
        score: 90,
        notes: "Candidato contratado",
        createdAt: new Date(),
        updatedAt: new Date()
    },
    {
        id: "2",
        candidateId: "2",
        vacancyId: "1",
        stage: "Interview",
        score: 75,
        notes: "Pendiente de entrevista",
        createdAt: new Date(),
        updatedAt: new Date()
    }
];

const vacancies: Vacancy[] = [
    {
        id: "1",
        title: "Senior Full-Stack Developer",
        companyName: "TechCorp Solutions",
        requiredSkills: ["TypeScript", "React", "Node.js"],
        preferredSkills: ["PostgreSQL", "Docker"],
        minYearsExperience: 4,
        maxYearsExperience: 8,
        requiredEnglishLevel: "B2",
        requiredSeniority: "Senior",
        salaryRangeMin: 5000,
        salaryRangeMax: 7000,
        isRemote: true,
        location: "Remote",
        status: "Open"
    },
    {
        id: "2",
        title: "Junior Java Developer",
        companyName: "Innovatech",
        requiredSkills: ["Java", "Spring"],
        preferredSkills: ["SQL", "Docker"],
        minYearsExperience: 1,
        maxYearsExperience: 3,
        requiredEnglishLevel: "B1",
        requiredSeniority: "Junior",
        salaryRangeMin: 2500,
        salaryRangeMax: 3500,
        isRemote: false,
        location: "Valencia",
        status: "Open"
    }
];

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