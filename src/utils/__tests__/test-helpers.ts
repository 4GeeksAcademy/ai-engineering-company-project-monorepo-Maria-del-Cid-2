import type {
  Candidate,
  Vacancy,
  SelectionProcess,
  SeniorityLevel,
  AvailabilityStatus,
  CandidateStatus,
  EnglishLevel,
  VacancyStatus,
  ProcessStage,
} from '../../types/models'

export function createCandidate(overrides: Partial<Candidate> = {}): Candidate {
  return {
    id: 'test-id',
    fullName: 'Test Candidate',
    email: 'test@example.com',
    phone: '600000000',
    yearsOfExperience: 5,
    skills: ['TypeScript', 'React'],
    englishLevel: 'C1' as EnglishLevel,
    seniority: 'Senior' as SeniorityLevel,
    currentSalary: 40000,
    expectedSalary: 50000,
    availability: 'Immediate' as AvailabilityStatus,
    location: 'Madrid',
    remoteOnly: false,
    status: 'Active' as CandidateStatus,
    ...overrides,
  }
}

export function createVacancy(overrides: Partial<Vacancy> = {}): Vacancy {
  return {
    id: 'vac-test-id',
    title: 'Test Vacancy',
    companyName: 'Test Corp',
    requiredSkills: ['TypeScript', 'React'],
    preferredSkills: ['Node.js'],
    minYearsExperience: 3,
    maxYearsExperience: 7,
    requiredEnglishLevel: 'B2' as EnglishLevel,
    requiredSeniority: 'Senior' as SeniorityLevel,
    salaryRangeMin: 5000,
    salaryRangeMax: 7000,
    isRemote: true,
    location: 'Remote',
    status: 'Open' as VacancyStatus,
    ...overrides,
  }
}

export function createProcess(overrides: Partial<SelectionProcess> = {}): SelectionProcess {
  return {
    id: 'proc-test-id',
    candidateId: 'test-id',
    vacancyId: 'vac-test-id',
    stage: 'Hired' as ProcessStage,
    score: 90,
    notes: 'Test process',
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date('2024-06-01'),
    ...overrides,
  }
}