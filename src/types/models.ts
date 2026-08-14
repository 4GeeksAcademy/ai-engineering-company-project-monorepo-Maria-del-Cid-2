/// ENTIDADES DE NEGOCIO
/// INTERFAZ CANDIDATO: 
type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "Native";
type SeniorityLevel = "Junior" | "Semi-Senior" | "Senior" | "Lead" | "Executive";
type AvailabilityStatus = "Immediate" | "2 weeks" | "1 month" | "Not available";
type CandidateStatus = "Active" | "In process" | "Hired" | "Inactive";

interface Candidate {
    id: string;
    fullName: string;
    email: string;
    phone: string;
    yearsOfExperience: number;
    skills: string[];
    englishLevel: EnglishLevel;
    seniority: SeniorityLevel;
    currentSalary: number;
    expectedSalary: number;
    availability: AvailabilityStatus;
    location: string;
    remoteOnly: boolean;
    status: CandidateStatus;
}
    
// INTERFAZ VACANTE: 
type VacancyStatus = "Open" | "In progress" | "Closed" | "On hold";

interface Vacancy {
    id: string;
    title: string;
    companyName: string;
    requiredSkills: string[];
    preferredSkills: string[];
    minYearsExperience: number;
    maxYearsExperience: number;
    requiredEnglishLevel: EnglishLevel;
    requiredSeniority: SeniorityLevel;
    salaryRangeMin: number;
    salaryRangeMax:number;
    isRemote: boolean;
    location: string;
    status: VacancyStatus;
}

//INTERFAZ SELECTIONPROCESS
type ProcessStage = "Screening" | "Interview" | "Technical test" | "Final interview" | "Offer" | "Rejected" | "Hired";

interface SelectionProcess {
    id: string;
    candidateId: string;
    vacancyId: string;
    stage: ProcessStage;
    score: number;
    notes: string;
    createdAt: Date;
    updatedAt: Date;
}