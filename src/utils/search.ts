//FUNCIONES DE OPERACIONES DE BÚSQUEDA

import { Candidate } from "../types/models";
import { sortCandidatesByExperience } from "./collections";

//función para buscar candidatos por ID
export function findCandidateById(candidates: Candidate[], id: string): Candidate | null {
for (let i = 0; i <  candidates.length; i++) {
    if (candidates[i].id === id) {
        return candidates[i];
    }
}
return null;
}

//Función para buscar candidatos por email
export function findCandidateByEmail(candidates: Candidate[], email: string): Candidate | null {
for (let i = 0; i < candidates.length; i++) {
    if (candidates[i].email.toLowerCase() === email.toLowerCase()) {
        return candidates[i];
    }
}
return null;
}

//función para buscar un candidato con un expected salary específico con búsqueda binaria
export function binarySearchCandidateBySalary(sortedCandidates: Candidate[], targetSalary: number): number {
    let left= 0;
    let right = sortedCandidates.length -1;
     while (left <= right)  {
        const middle = Math.floor((left + right)/ 2);
        if (sortedCandidates[middle].expectedSalary === targetSalary) {
        return middle;
     } else if (sortedCandidates[middle].expectedSalary < targetSalary) {
        left = middle + 1;
     } else {
        right = middle - 1;
     }

     }
     return -1;
}



