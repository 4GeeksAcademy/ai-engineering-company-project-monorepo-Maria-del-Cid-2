import { describe, it, expect } from '@jest/globals'
import {
  countCandidatesByStatus,
  calculateAverageSalary,
  findTopSkills,
  calculateVacancyFillRate,
  calculateCandidateScore,
  rankCandidatesForVacancy,
  groupCandidatesBySeniority,
} from '../transformations'
import { createCandidate, createVacancy, createProcess } from './test-helpers'
import type { Candidate, SeniorityLevel, EnglishLevel, AvailabilityStatus, CandidateStatus, ProcessStage } from '../../types/models'

// ---------------------------------------------------------------------------
// countCandidatesByStatus
// ---------------------------------------------------------------------------
describe('countCandidatesByStatus', () => {
  it('returns zero for all statuses when the array is empty', () => {
    const result = countCandidatesByStatus([])
    expect(result).toEqual({ Active: 0, 'In process': 0, Hired: 0, Inactive: 0 })
  })

  it('counts candidates correctly', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', status: 'Active' as CandidateStatus }),
      createCandidate({ id: '2', status: 'Active' as CandidateStatus }),
      createCandidate({ id: '3', status: 'In process' as CandidateStatus }),
      createCandidate({ id: '4', status: 'Hired' as CandidateStatus }),
    ]
    const result = countCandidatesByStatus(candidates)
    expect(result.Active).toBe(2)
    expect(result['In process']).toBe(1)
    expect(result.Hired).toBe(1)
    expect(result.Inactive).toBe(0)
  })

  it('only counts Active when all candidates are Active', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', status: 'Active' as CandidateStatus }),
      createCandidate({ id: '2', status: 'Active' as CandidateStatus }),
    ]
    const result = countCandidatesByStatus(candidates)
    expect(result).toEqual({ Active: 2, 'In process': 0, Hired: 0, Inactive: 0 })
  })
})

// ---------------------------------------------------------------------------
// calculateAverageSalary
// ---------------------------------------------------------------------------
describe('calculateAverageSalary', () => {
  it('returns 0 for an empty array', () => {
    expect(calculateAverageSalary([])).toBe(0)
  })

  it('returns the salary for a single candidate', () => {
    const candidates: Candidate[] = [
      createCandidate({ expectedSalary: 40000 }),
    ]
    expect(calculateAverageSalary(candidates)).toBe(40000)
  })

  it('calculates the average of multiple candidates', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', expectedSalary: 30000 }),
      createCandidate({ id: '2', expectedSalary: 50000 }),
    ]
    expect(calculateAverageSalary(candidates)).toBe(40000)
  })

  it('rounds to two decimal places', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', expectedSalary: 10000 }),
      createCandidate({ id: '2', expectedSalary: 10001 }),
    ]
    expect(calculateAverageSalary(candidates)).toBe(10000.5)
  })

  it('handles fractional averages correctly', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', expectedSalary: 10000 }),
      createCandidate({ id: '2', expectedSalary: 10000 }),
      createCandidate({ id: '3', expectedSalary: 10001 }),
    ]
    const avg = calculateAverageSalary(candidates)
    expect(avg).toBe(10000.33)
  })
})

// ---------------------------------------------------------------------------
// findTopSkills
// ---------------------------------------------------------------------------
describe('findTopSkills', () => {
  it('returns empty array for empty candidates', () => {
    expect(findTopSkills([], 3)).toEqual([])
  })

  it('returns top N skills sorted by frequency descending', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', skills: ['TypeScript', 'React'] }),
      createCandidate({ id: '2', skills: ['TypeScript', 'Node.js'] }),
      createCandidate({ id: '3', skills: ['React', 'Python'] }),
    ]
    const result = findTopSkills(candidates, 2)
    expect(result).toHaveLength(2)
    expect(result[0].skill).toBe('TypeScript')
    expect(result[0].count).toBe(2)
    expect(result[1].count).toBe(2) // React and TypeScript both have 2; order may vary for ties
  })

  it('returns all skills when topN exceeds unique skill count', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', skills: ['TypeScript'] }),
    ]
    const result = findTopSkills(candidates, 10)
    expect(result).toHaveLength(1)
    expect(result[0]).toEqual({ skill: 'TypeScript', count: 1 })
  })

  it('returns empty when topN is 0', () => {
    const candidates: Candidate[] = [
      createCandidate({ skills: ['TypeScript'] }),
    ]
    expect(findTopSkills(candidates, 0)).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// calculateVacancyFillRate
// ---------------------------------------------------------------------------
describe('calculateVacancyFillRate', () => {
  it('returns 0 for empty processes', () => {
    expect(calculateVacancyFillRate([])).toBe(0)
  })

  it('returns 100 when all processes are Hired', () => {
    const processes = [
      createProcess({ id: '1', stage: 'Hired' as ProcessStage }),
      createProcess({ id: '2', stage: 'Hired' as ProcessStage }),
    ]
    expect(calculateVacancyFillRate(processes)).toBe(100)
  })

  it('returns 0 when no process is Hired', () => {
    const processes = [
      createProcess({ id: '1', stage: 'Interview' as ProcessStage }),
      createProcess({ id: '2', stage: 'Screening' as ProcessStage }),
    ]
    expect(calculateVacancyFillRate(processes)).toBe(0)
  })

  it('calculates partial fill rate', () => {
    const processes = [
      createProcess({ id: '1', stage: 'Hired' as ProcessStage }),
      createProcess({ id: '2', stage: 'Interview' as ProcessStage }),
    ]
    expect(calculateVacancyFillRate(processes)).toBe(50)
  })

  it('rounds to two decimal places', () => {
    const processes = [
      createProcess({ id: '1', stage: 'Hired' as ProcessStage }),
      createProcess({ id: '2', stage: 'Interview' as ProcessStage }),
      createProcess({ id: '3', stage: 'Interview' as ProcessStage }),
    ]
    expect(calculateVacancyFillRate(processes)).toBe(33.33)
  })
})

// ---------------------------------------------------------------------------
// calculateCandidateScore (highest-priority function)
// ---------------------------------------------------------------------------
describe('calculateCandidateScore', () => {
  // --- Required Skills scoring (max 40) ---
  it('awards 40 points when candidate has 100% of required skills', () => {
    const candidate = createCandidate({ skills: ['TypeScript', 'React', 'Node.js'] })
    const vacancy = createVacancy({ requiredSkills: ['TypeScript', 'React'] })
    const score = calculateCandidateScore(candidate, vacancy)
    // 40 (100% required) + preferred + experience + seniority + english + salary
    expect(score).toBeGreaterThanOrEqual(40)
  })

  it('awards 20 points when candidate has >= 50% of required skills', () => {
    const candidate = createCandidate({ skills: ['TypeScript'] })
    const vacancy = createVacancy({ requiredSkills: ['TypeScript', 'React'] })
    const score = calculateCandidateScore(candidate, vacancy)
    expect(score).toBeGreaterThanOrEqual(20)
  })

  it('awards 0 points when candidate has < 50% of required skills', () => {
    const candidate = createCandidate({
      skills: ['Python'],
      // Also fail every other category to isolate
      yearsOfExperience: 0,
      seniority: 'Junior' as SeniorityLevel,
      englishLevel: 'A1' as EnglishLevel,
      expectedSalary: 10000,
    })
    const vacancy = createVacancy({ requiredSkills: ['TypeScript', 'React'] })
    const score = calculateCandidateScore(candidate, vacancy)
    // 0 req skills + 0 pref + 0 exp + 0 seniority + 0 english + 0 salary = 0
    expect(score).toBe(0)
  })

  // --- Preferred Skills scoring (max 20, capped at 2 matches × 10) ---
  it('awards up to 20 points for preferred skills', () => {
    const candidate = createCandidate({ skills: ['TypeScript', 'React', 'Node.js', 'PostgreSQL', 'Docker'] })
    const vacancy = createVacancy({ preferredSkills: ['PostgreSQL', 'Docker', 'Kubernetes', 'AWS'] })
    const score = calculateCandidateScore(candidate, vacancy)
    expect(score).toBeGreaterThanOrEqual(20) // 2 matches × 10 = 20, capped
  })

  // --- Experience scoring (max 20, or 10 if diff <= 2) ---
  it('awards 20 points when experience is within range', () => {
    const candidate = createCandidate({ yearsOfExperience: 5 })
    const vacancy = createVacancy({ minYearsExperience: 3, maxYearsExperience: 7 })
    const score = calculateCandidateScore(candidate, vacancy)
    expect(score).toBeGreaterThanOrEqual(20)
  })

  it('awards 10 points when experience difference is <= 2 years', () => {
    const candidate = createCandidate({ yearsOfExperience: 2 })
    const vacancy = createVacancy({ minYearsExperience: 3, maxYearsExperience: 7 })
    const score = calculateCandidateScore(candidate, vacancy)
    // difference = 1 (candidate below min by 1), should get 10
    expect(score).toBeGreaterThanOrEqual(10)
  })

  it('awards 0 extra points when experience difference is > 2 years', () => {
    const candidate = createCandidate({ yearsOfExperience: 0 })
    const vacancy = createVacancy({ minYearsExperience: 5, maxYearsExperience: 10 })
    const score = calculateCandidateScore(candidate, vacancy)
    // Default candidate has skills matching vacancy's requiredSkills (TypeScript, React) → +40
    // No preferred skills match → +0
    // Diff=5 (exp outside range by >2) → +0
    // Seniority match (Senior/Senior) → +15
    // English C1 >= B2 → +15
    // Salary 50000 > 8400 → +0
    // Total = 40 + 0 + 0 + 15 + 15 + 0 = 70
    expect(score).toBe(70)
  })

  // --- Seniority scoring (max 15, or 7 if 1 level apart) ---
  it('awards 15 points for exact seniority match', () => {
    const candidate = createCandidate({ seniority: 'Senior' as SeniorityLevel, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ requiredSeniority: 'Senior' as SeniorityLevel })
    const score = calculateCandidateScore(candidate, vacancy)
    // Isolate: candidate matches required skills => 40 at least
    expect(score).toBeGreaterThanOrEqual(40 + 15)
  })

  it('awards 7 points when seniority is 1 level apart', () => {
    const candidate = createCandidate({ seniority: 'Semi-Senior' as SeniorityLevel, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ requiredSeniority: 'Senior' as SeniorityLevel })
    const score = calculateCandidateScore(candidate, vacancy)
    expect(score).toBeGreaterThanOrEqual(40 + 7)
  })

  it('awards 0 extra points when seniority is 2+ levels apart', () => {
    const candidate = createCandidate({ seniority: 'Junior' as SeniorityLevel, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ requiredSeniority: 'Lead' as SeniorityLevel })
    const score = calculateCandidateScore(candidate, vacancy)
    // 40 (req) + 0 pref + 20 exp + 0 seniority (diff=3) + 15 english + 0 salary = 75
    expect(score).toBe(75)
  })

  // --- English level scoring (max 15) ---
  it('awards 15 points when candidate English level >= required', () => {
    const candidate = createCandidate({ englishLevel: 'C1' as EnglishLevel, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ requiredEnglishLevel: 'B2' as EnglishLevel })
    const score = calculateCandidateScore(candidate, vacancy)
    expect(score).toBeGreaterThanOrEqual(40 + 15 + 20) // req skills + english + experience
  })

  it('awards 0 points when candidate English level < required', () => {
    const candidate = createCandidate({ englishLevel: 'A2' as EnglishLevel, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ requiredEnglishLevel: 'B2' as EnglishLevel })
    const score = calculateCandidateScore(candidate, vacancy)
    // 40 (req) + 0 pref + 20 exp + 15 seniority + 0 english (A2 < B2) + 0 salary = 75
    expect(score).toBe(75)
  })

  // --- Salary scoring (max 10, or 5 if <= 120% of max) ---
  it('awards 10 points when expected salary is within range', () => {
    const candidate = createCandidate({ expectedSalary: 6000, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ salaryRangeMin: 5000, salaryRangeMax: 7000 })
    const score = calculateCandidateScore(candidate, vacancy)
    expect(score).toBeGreaterThanOrEqual(40 + 20 + 15 + 10 + 10) // req + exp + seniority + english + salary
  })

  it('awards 5 points when expected salary is up to 20% above max', () => {
    const candidate = createCandidate({ expectedSalary: 8000, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ salaryRangeMin: 5000, salaryRangeMax: 7000 })
    const score = calculateCandidateScore(candidate, vacancy)
    // 8000 <= 7000 * 1.20 = 8400, so 5 extra points
    expect(score).toBeGreaterThanOrEqual(40 + 20 + 15 + 5)
  })

  it('awards 0 salary points when expected salary > 120% of max', () => {
    const candidate = createCandidate({ expectedSalary: 9000, skills: ['TypeScript', 'React'] })
    const vacancy = createVacancy({ salaryRangeMin: 5000, salaryRangeMax: 7000 })
    const score = calculateCandidateScore(candidate, vacancy)
    // 9000 > 8400, so 0 salary points
    // 40 (req) + 0 pref + 20 exp (within) + 15 seniority + 15 english + 0 salary = 90
    expect(score).toBe(90)
  })

  // --- Integration: full match scenario ---
  it('produces a high score for a perfect match', () => {
    const candidate = createCandidate({
      skills: ['TypeScript', 'React', 'Node.js', 'PostgreSQL'],
      yearsOfExperience: 5,
      seniority: 'Senior' as SeniorityLevel,
      englishLevel: 'C1' as EnglishLevel,
      expectedSalary: 6000,
    })
    const vacancy = createVacancy({
      requiredSkills: ['TypeScript', 'React'],
      preferredSkills: ['Node.js', 'PostgreSQL'],
      minYearsExperience: 3,
      maxYearsExperience: 7,
      requiredSeniority: 'Senior' as SeniorityLevel,
      requiredEnglishLevel: 'B2' as EnglishLevel,
      salaryRangeMin: 5000,
      salaryRangeMax: 7000,
    })
    const score = calculateCandidateScore(candidate, vacancy)
    // 40 (100% req skills) + 20 (2 pref skills × 10, capped) + 20 (exp within) + 15 (seniority match) + 15 (english) + 10 (salary within) = 120
    expect(score).toBe(120)
  })

  // --- Edge: candidate with no matching skills at all ---
  it('returns 0 for a completely non-matching candidate', () => {
    const candidate = createCandidate({
      skills: ['Python'],
      yearsOfExperience: 10,
      seniority: 'Junior' as SeniorityLevel,
      englishLevel: 'A1' as EnglishLevel,
      expectedSalary: 10000,
    })
    const vacancy = createVacancy({
      requiredSkills: ['TypeScript'],
      preferredSkills: ['Node.js'],
      minYearsExperience: 3,
      maxYearsExperience: 7,
      requiredSeniority: 'Senior' as SeniorityLevel,
      requiredEnglishLevel: 'C1' as EnglishLevel,
      salaryRangeMin: 5000,
      salaryRangeMax: 7000,
    })
    const score = calculateCandidateScore(candidate, vacancy)
    // 0 req skills, 0 pref skills, 0 exp (diff=3), 0 seniority (diff=3), 0 english (A1 < C1), 0 salary (10k > 8400)
    expect(score).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// rankCandidatesForVacancy
// ---------------------------------------------------------------------------
describe('rankCandidatesForVacancy', () => {
  it('returns an empty array when there are no candidates', () => {
    expect(rankCandidatesForVacancy([], createVacancy())).toEqual([])
  })

  it('returns candidates sorted by score descending', () => {
    const weak = createCandidate({
      id: 'weak',
      skills: ['Python'],
      yearsOfExperience: 10,
      seniority: 'Junior' as SeniorityLevel,
      englishLevel: 'A1' as EnglishLevel,
      expectedSalary: 10000,
    })
    const strong = createCandidate({
      id: 'strong',
      skills: ['TypeScript', 'React'],
      yearsOfExperience: 5,
      seniority: 'Senior' as SeniorityLevel,
      englishLevel: 'C1' as EnglishLevel,
      expectedSalary: 6000,
    })
    const vacancy = createVacancy()
    const results = rankCandidatesForVacancy([weak, strong], vacancy)
    expect(results).toHaveLength(2)
    expect(results[0].candidate.id).toBe('strong')
    expect(results[1].candidate.id).toBe('weak')
    expect(results[0].score).toBeGreaterThan(results[1].score)
  })

  it('preserves candidate reference in result', () => {
    const candidate = createCandidate({ id: 'keep-me' })
    const results = rankCandidatesForVacancy([candidate], createVacancy())
    expect(results[0].candidate).toBe(candidate)
  })
})

// ---------------------------------------------------------------------------
// groupCandidatesBySeniority
// ---------------------------------------------------------------------------
describe('groupCandidatesBySeniority', () => {
  it('returns empty groups for an empty array', () => {
    const result = groupCandidatesBySeniority([])
    expect(result.Junior).toEqual([])
    expect(result['Semi-Senior']).toEqual([])
    expect(result.Senior).toEqual([])
    expect(result.Lead).toEqual([])
    expect(result.Executive).toEqual([])
  })

  it('groups candidates by seniority', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', seniority: 'Senior' as SeniorityLevel }),
      createCandidate({ id: '2', seniority: 'Junior' as SeniorityLevel }),
      createCandidate({ id: '3', seniority: 'Senior' as SeniorityLevel }),
    ]
    const result = groupCandidatesBySeniority(candidates)
    expect(result.Senior).toHaveLength(2)
    expect(result.Junior).toHaveLength(1)
    expect(result['Semi-Senior']).toHaveLength(0)
    expect(result.Lead).toHaveLength(0)
    expect(result.Executive).toHaveLength(0)
  })

  it('puts all candidates in the same group when they share seniority', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', seniority: 'Lead' as SeniorityLevel }),
      createCandidate({ id: '2', seniority: 'Lead' as SeniorityLevel }),
    ]
    const result = groupCandidatesBySeniority(candidates)
    expect(result.Lead).toHaveLength(2)
    expect(result.Senior).toHaveLength(0)
  })
})