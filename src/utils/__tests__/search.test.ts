import { describe, it, expect } from '@jest/globals'
import { findCandidateById, findCandidateByEmail, binarySearchCandidateBySalary } from '../search'
import { createCandidate } from './test-helpers'
import type { Candidate } from '../../types/models'

// ---------------------------------------------------------------------------
// findCandidateById
// ---------------------------------------------------------------------------
describe('findCandidateById', () => {
  it('returns the candidate when id matches', () => {
    const candidates = [createCandidate({ id: '1' })]
    const result = findCandidateById(candidates, '1')
    expect(result).not.toBeNull()
    expect(result!.id).toBe('1')
  })

  it('returns null when id does not match', () => {
    const candidates = [createCandidate({ id: '1' })]
    expect(findCandidateById(candidates, '999')).toBeNull()
  })

  it('returns null for an empty array', () => {
    expect(findCandidateById([], '1')).toBeNull()
  })

  it('returns the first match when multiple candidates exist', () => {
    const candidates = [
      createCandidate({ id: 'a' }),
      createCandidate({ id: 'b' }),
      createCandidate({ id: 'c' }),
    ]
    const result = findCandidateById(candidates, 'b')
    expect(result!.id).toBe('b')
  })
})

// ---------------------------------------------------------------------------
// findCandidateByEmail
// ---------------------------------------------------------------------------
describe('findCandidateByEmail', () => {
  it('returns the candidate when email matches', () => {
    const candidates = [createCandidate({ email: 'user@example.com' })]
    const result = findCandidateByEmail(candidates, 'user@example.com')
    expect(result).not.toBeNull()
    expect(result!.email).toBe('user@example.com')
  })

  it('returns null when email does not match', () => {
    const candidates = [createCandidate({ email: 'user@example.com' })]
    expect(findCandidateByEmail(candidates, 'other@example.com')).toBeNull()
  })

  it('returns null for an empty array', () => {
    expect(findCandidateByEmail([], 'a@b.com')).toBeNull()
  })

  it('is case-insensitive', () => {
    const candidates = [createCandidate({ email: 'User@Example.com' })]
    const result = findCandidateByEmail(candidates, 'user@example.com')
    expect(result).not.toBeNull()
    expect(result!.email).toBe('User@Example.com')
  })

  it('is case-insensitive on query email', () => {
    const candidates = [createCandidate({ email: 'user@example.com' })]
    const result = findCandidateByEmail(candidates, 'USER@EXAMPLE.COM')
    expect(result).not.toBeNull()
    expect(result!.email).toBe('user@example.com')
  })
})

// ---------------------------------------------------------------------------
// binarySearchCandidateBySalary
// ---------------------------------------------------------------------------
describe('binarySearchCandidateBySalary', () => {
  it('returns the index when target salary is found', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 10000 }),
      createCandidate({ id: 'b', expectedSalary: 20000 }),
      createCandidate({ id: 'c', expectedSalary: 30000 }),
    ]
    const idx = binarySearchCandidateBySalary(candidates, 20000)
    expect(idx).toBe(1)
  })

  it('returns -1 when target salary is not in the array', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 10000 }),
      createCandidate({ id: 'b', expectedSalary: 20000 }),
      createCandidate({ id: 'c', expectedSalary: 30000 }),
    ]
    expect(binarySearchCandidateBySalary(candidates, 25000)).toBe(-1)
  })

  it('returns -1 for an empty array', () => {
    expect(binarySearchCandidateBySalary([], 10000)).toBe(-1)
  })

  it('finds the salary when array has one element matching', () => {
    const candidates: Candidate[] = [
      createCandidate({ expectedSalary: 35000 }),
    ]
    expect(binarySearchCandidateBySalary(candidates, 35000)).toBe(0)
  })

  it('returns -1 when target is below all salaries', () => {
    const candidates: Candidate[] = [
      createCandidate({ expectedSalary: 30000 }),
      createCandidate({ expectedSalary: 40000 }),
    ]
    expect(binarySearchCandidateBySalary(candidates, 10000)).toBe(-1)
  })

  it('returns -1 when target is above all salaries', () => {
    const candidates: Candidate[] = [
      createCandidate({ expectedSalary: 30000 }),
      createCandidate({ expectedSalary: 40000 }),
    ]
    expect(binarySearchCandidateBySalary(candidates, 50000)).toBe(-1)
  })

  it('works with duplicate salary values (first found may differ)', () => {
    const candidates: Candidate[] = [
      createCandidate({ id: 'a', expectedSalary: 30000 }),
      createCandidate({ id: 'b', expectedSalary: 30000 }),
      createCandidate({ id: 'c', expectedSalary: 40000 }),
    ]
    const idx = binarySearchCandidateBySalary(candidates, 30000)
    // Binary search may return any matching index; just check it found one
    expect(idx).toBeGreaterThanOrEqual(0)
    expect(candidates[idx].expectedSalary).toBe(30000)
  })
})