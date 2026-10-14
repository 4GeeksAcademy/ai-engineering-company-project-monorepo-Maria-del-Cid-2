import { describe, it, expect } from '@jest/globals'
import {
  filterCandidatesBySkills,
  filterCandidatesBySeniority,
  filterCandidatesByAvailability,
  sortCandidatesBySalary,
  sortCandidatesByExperience,
} from '../collections'
import { createCandidate } from './test-helpers'
import type { Candidate, SeniorityLevel, AvailabilityStatus } from '../../types/models'

// ---------------------------------------------------------------------------
// filterCandidatesBySkills
// ---------------------------------------------------------------------------
describe('filterCandidatesBySkills', () => {
  it('returns candidates that have ALL required skills', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', skills: ['TypeScript', 'React'] }),
      createCandidate({ id: '2', skills: ['TypeScript', 'Node.js'] }),
    ]
    const result = filterCandidatesBySkills(candidates, ['TypeScript', 'React'])
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('1')
  })

  it('returns empty array when no candidate has all skills', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', skills: ['Python'] }),
      createCandidate({ id: '2', skills: ['Java'] }),
    ]
    expect(filterCandidatesBySkills(candidates, ['TypeScript', 'React'])).toEqual([])
  })

  it('returns empty array when candidates list is empty', () => {
    expect(filterCandidatesBySkills([], ['TypeScript'])).toEqual([])
  })

  it('is case-insensitive', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', skills: ['typescript', 'react'] }),
    ]
    const result = filterCandidatesBySkills(candidates, ['TypeScript', 'React'])
    expect(result).toHaveLength(1)
  })

  it('returns empty when requiredSkills is empty', () => {
    const candidates: Candidate[] = [createCandidate({ id: '1', skills: ['TypeScript'] })]
    // .every() on an empty array returns true, so the filter passes every candidate
    const result = filterCandidatesBySkills(candidates, [])
    expect(result).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------
// filterCandidatesBySeniority
// ---------------------------------------------------------------------------
describe('filterCandidatesBySeniority', () => {
  it('returns candidates with matching seniority', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', seniority: 'Senior' as SeniorityLevel }),
      createCandidate({ id: '2', seniority: 'Junior' as SeniorityLevel }),
    ]
    const result = filterCandidatesBySeniority(candidates, 'Senior' as SeniorityLevel)
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('1')
  })

  it('returns empty array when no candidate matches', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', seniority: 'Junior' as SeniorityLevel }),
    ]
    expect(filterCandidatesBySeniority(candidates, 'Lead' as SeniorityLevel)).toEqual([])
  })

  it('returns empty array when candidates list is empty', () => {
    expect(filterCandidatesBySeniority([], 'Senior' as SeniorityLevel)).toEqual([])
  })

  it('handles multiple candidates with same seniority', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', seniority: 'Senior' as SeniorityLevel }),
      createCandidate({ id: '2', seniority: 'Senior' as SeniorityLevel }),
    ]
    expect(filterCandidatesBySeniority(candidates, 'Senior' as SeniorityLevel)).toHaveLength(2)
  })
})

// ---------------------------------------------------------------------------
// filterCandidatesByAvailability
// ---------------------------------------------------------------------------
describe('filterCandidatesByAvailability', () => {
  it('returns candidates whose availability matches any of the provided statuses', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: '1', availability: 'Immediate' as AvailabilityStatus }),
      createCandidate({ id: '2', availability: '2 weeks' as AvailabilityStatus }),
      createCandidate({ id: '3', availability: 'Not available' as AvailabilityStatus }),
    ]
    const result = filterCandidatesByAvailability(candidates, ['Immediate' as AvailabilityStatus, '2 weeks' as AvailabilityStatus])
    expect(result).toHaveLength(2)
    expect(result.map(c => c.id)).toEqual(['1', '2'])
  })

  it('returns empty array when no candidate matches', () => {
    const candidates: Candidate[] = [
      createCandidate({ availability: 'Not available' as AvailabilityStatus }),
    ]
    expect(filterCandidatesByAvailability(candidates, ['Immediate' as AvailabilityStatus])).toEqual([])
  })

  it('returns empty array when candidates list is empty', () => {
    expect(filterCandidatesByAvailability([], ['Immediate' as AvailabilityStatus])).toEqual([])
  })

  it('returns empty when availability filter is empty', () => {
    const candidates: Candidate[] = [
      createCandidate({ availability: 'Immediate' as AvailabilityStatus }),
    ]
    expect(filterCandidatesByAvailability(candidates, [])).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// sortCandidatesBySalary
// ---------------------------------------------------------------------------
describe('sortCandidatesBySalary', () => {
  it('sorts ascending', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 50000 }),
      createCandidate({ id: 'b', expectedSalary: 30000 }),
      createCandidate({ id: 'c', expectedSalary: 40000 }),
    ]
    const result = sortCandidatesBySalary(candidates, 'asc')
    expect(result.map(c => c.expectedSalary)).toEqual([30000, 40000, 50000])
  })

  it('sorts descending', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 30000 }),
      createCandidate({ id: 'b', expectedSalary: 50000 }),
      createCandidate({ id: 'c', expectedSalary: 40000 }),
    ]
    const result = sortCandidatesBySalary(candidates, 'desc')
    expect(result.map(c => c.expectedSalary)).toEqual([50000, 40000, 30000])
  })

  it('returns a new array (does not mutate input)', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 50000 }),
      createCandidate({ id: 'b', expectedSalary: 30000 }),
    ]
    const original = [...candidates]
    const result = sortCandidatesBySalary(candidates, 'asc')
    expect(result).not.toBe(candidates)
    // original order unchanged
    expect(candidates[0].expectedSalary).toBe(50000)
  })

  it('returns empty for empty input', () => {
    expect(sortCandidatesBySalary([], 'asc')).toEqual([])
  })

  it('handles single element', () => {
    const candidates: Candidate[] = [createCandidate({ expectedSalary: 40000 })]
    expect(sortCandidatesBySalary(candidates, 'asc')).toHaveLength(1)
  })

  it('handles equal salaries', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 40000 }),
      createCandidate({ id: 'b', expectedSalary: 40000 }),
    ]
    const result = sortCandidatesBySalary(candidates, 'asc')
    expect(result.map(c => c.expectedSalary)).toEqual([40000, 40000])
  })
})

// ---------------------------------------------------------------------------
// sortCandidatesByExperience
// ---------------------------------------------------------------------------
describe('sortCandidatesByExperience', () => {
  it('sorts ascending', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', yearsOfExperience: 10 }),
      createCandidate({ id: 'b', yearsOfExperience: 3 }),
      createCandidate({ id: 'c', yearsOfExperience: 7 }),
    ]
    const result = sortCandidatesByExperience(candidates, 'asc')
    expect(result.map(c => c.yearsOfExperience)).toEqual([3, 7, 10])
  })

  it('sorts descending', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', yearsOfExperience: 3 }),
      createCandidate({ id: 'b', yearsOfExperience: 10 }),
      createCandidate({ id: 'c', yearsOfExperience: 7 }),
    ]
    const result = sortCandidatesByExperience(candidates, 'desc')
    expect(result.map(c => c.yearsOfExperience)).toEqual([10, 7, 3])
  })

  it('returns a new array (does not mutate input)', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', yearsOfExperience: 10 }),
      createCandidate({ id: 'b', yearsOfExperience: 3 }),
    ]
    const result = sortCandidatesByExperience(candidates, 'asc')
    expect(result).not.toBe(candidates)
  })

  it('returns empty for empty input', () => {
    expect(sortCandidatesByExperience([], 'asc')).toEqual([])
  })

  it('handles single element', () => {
    const candidates: Candidate[] = [createCandidate({ yearsOfExperience: 5 })]
    expect(sortCandidatesByExperience(candidates, 'asc')).toHaveLength(1)
  })

  it('handles equal experience values', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', yearsOfExperience: 5 }),
      createCandidate({ id: 'b', yearsOfExperience: 5 }),
    ]
    const result = sortCandidatesByExperience(candidates, 'desc')
    expect(result.map(c => c.yearsOfExperience)).toEqual([5, 5])
  })
})