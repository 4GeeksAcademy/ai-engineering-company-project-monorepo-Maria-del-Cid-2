import { filterCandidatesBySkills,  filterCandidatesBySeniority,  filterCandidatesByAvailability, sortCandidatesBySalary, sortCandidatesByExperience } from "./collections";
import { Candidate } from "../types/models";

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