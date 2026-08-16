import { Candidate } from "../types/models";

// función para devolver los candidatos que cuentan con TODAS las habilidades requeridas (matching de habilidades, case-intensitive)
export function filterCandidatesBySkills(candidates: Candidate[], requiredSkills: string[]): Candidate[]{


return candidates.filter (candidate => requiredSkills.every(requiredSkill => 
    candidate.skills.some(candidateSkill => candidateSkill.toLowerCase() === requiredSkill.toLowerCase()
  )
 )
) 
}

// función para devolver candidatos de nivel senior
export function filterCandidatesBySeniority(candidates: Candidate[], seniority: SeniorityLevel): Candidate[]{
return candidates.filter (candidate => candidate.seniority === seniority);
}

// función para candidatos con la misma disponibilidad que la requerida en la oferta
export function filterCandidatesByAvailability(candidates: Candidate[], availability: AvailabilityStatus[]): Candidate[]{
return candidates.filter (candidate => availability.some(status => status === candidate.availability));
}

// función para candidatos ordenados por salario esperado..
export function sortCandidatesBySalary(candidates: Candidate[], order: "asc" | "desc"): Candidate[]{
const sortedCandidates = [ ... candidates];
sortedCandidates.sort((a, b) => {
    if (order === "asc") {
        return a.expectedSalary - b.expectedSalary;
    } else {
        return b.expectedSalary - a.expectedSalary;
    }
})
return sortedCandidates;
}

//función que ordena a los candidatos según la experiencia que tienen. 
export function sortCandidatesByExperience(candidates: Candidate[], order: "asc" | "desc"): Candidate[] {
    const sortedCandidates =  [ ... candidates];
    sortedCandidates.sort((a,b) => {
        if ( order === "asc" ){
        return a.yearsOfExperience - b.yearsOfExperience;
    } else {
        return b.yearsOfExperience - a.yearsOfExperience;
    }
})
return sortedCandidates;
}