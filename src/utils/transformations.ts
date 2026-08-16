import { Candidate, CandidateStatus, SelectionProcess} from "../types/models";
// AGREGACIONES Y REPORTES

//Función que muestra el conteo de candidatos por cada estado.
export function countCandidatesByStatus(candidates: Candidate[]): Record<CandidateStatus, number> {
const result: Record<CandidateStatus, number> = {
    Active: 0,
    "In process": 0,
    Hired: 0,
    Inactive: 0,
}
candidates.reduce((acumulador, candidate) => {
    acumulador[candidate.status]++;
    return acumulador;
 }, result);
 return result;
}

// Calcular el salario promedio esperado de los candidatos
export function calculateAverageSalary(candidates: Candidate[]): number {
const totalSalary = candidates.reduce((total, candidate) => {
    return total + candidate.expectedSalary;
}, 0);
const averageSalary = totalSalary / candidates.length;

return Number(averageSalary.toFixed(2));
}

//Función que encuentra las habilidades más frecuentes entre todos los candidatos y las devuelve ordenadas de mayor a menor frecuencia. 
export function findTopSkills(candidates: Candidate[], topN: number): Array<{skill: string, count: number}> {
    const skillCounts: Record<string, number> = {}
    candidates.forEach(candidate => {
        candidate.skills.forEach(skill => {
            if (skillCounts[skill]) {
                skillCounts[skill]++;
            } else {
                skillCounts[skill] = 1;
            }
        });
    });
            const skillsArray = Object.entries(skillCounts).map(([skill, count]) => {
                return { skill, count};
            });
            skillsArray.sort((a, b) => b.count - a.count);
            return skillsArray.slice(0,topN);
        }  


// Función para calcular el porcentaje de vacantes que han acabado con contratos.
export function calculateVacancyFillRate(processes: SelectionProcess[]): number{
const hiredCount = processes.reduce((count, process) => {
    if (process.stage === "Hired"){
    return count + 1;
}
return count;
}, 0);
const fillRate = (hiredCount / processes.length) * 100;
return Number (fillRate.toFixed(2));

}


            

    