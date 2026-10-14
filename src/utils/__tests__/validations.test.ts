import { describe, it, expect } from '@jest/globals'
import { validateCandidate, isValidEmail, validateVacancy } from '../validations'
import { createCandidate, createVacancy } from './test-helpers'
import type { EnglishLevel, SeniorityLevel, VacancyStatus, AvailabilityStatus, CandidateStatus } from '../../types/models'

// ---------------------------------------------------------------------------
// isValidEmail
// ---------------------------------------------------------------------------
describe('isValidEmail', () => {
  it('returns true for a standard email', () => {
    expect(isValidEmail('user@domain.com')).toBe(true)
  })

  it('returns false when there is no @', () => {
    expect(isValidEmail('usermail.com')).toBe(false)
  })

  it('returns false when @ is at the beginning', () => {
    expect(isValidEmail('@domain.com')).toBe(false)
  })

  it('returns false when there is no dot after @', () => {
    expect(isValidEmail('user@domain')).toBe(false)
  })

  it('returns false when dot immediately follows @', () => {
    expect(isValidEmail('user@.com')).toBe(false)
  })

  it('returns false for an empty string', () => {
    expect(isValidEmail('')).toBe(false)
  })

  it('returns true for email with subdomain', () => {
    expect(isValidEmail('user@sub.domain.com')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// validateCandidate
// ---------------------------------------------------------------------------
describe('validateCandidate', () => {
  it('returns valid for a correct candidate', () => {
    const c = createCandidate()
    const result = validateCandidate(c)
    expect(result.valid).toBe(true)
    expect(result.errors).toEqual([])
  })

  it('returns error when yearsOfExperience < 0', () => {
    const c = createCandidate({ yearsOfExperience: -1 })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Los años de experiencia deben de estar entre 0 y 50')
  })

  it('returns error when yearsOfExperience > 50', () => {
    const c = createCandidate({ yearsOfExperience: 51 })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Los años de experiencia deben de estar entre 0 y 50')
  })

  it('returns error when currentSalary <= 0', () => {
    const c = createCandidate({ currentSalary: 0 })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('El salario actual debe de ser mayor que 0')
  })

  it('returns error when expectedSalary <= 0', () => {
    const c = createCandidate({ expectedSalary: 0 })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('El salario estimado debe de ser mayor que 0')
  })

  it('returns error when skills is empty', () => {
    const c = createCandidate({ skills: [] })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Debe incluir al menos una habilidad')
  })

  it('returns error when email is invalid', () => {
    const c = createCandidate({ email: 'invalid' })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('El correo electrónico introducido no es válido')
  })

  it('returns error when phone is empty', () => {
    const c = createCandidate({ phone: '' })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Debe incluir un número de telefono')
  })

  it('accumulates multiple errors', () => {
    const c = createCandidate({
      yearsOfExperience: 55,
      currentSalary: 0,
      expectedSalary: 0,
      skills: [],
      email: 'bad',
      phone: '',
    })
    const result = validateCandidate(c)
    expect(result.valid).toBe(false)
    expect(result.errors.length).toBeGreaterThanOrEqual(6)
  })

  it('accepts boundary yearsOfExperience = 0', () => {
    const c = createCandidate({ yearsOfExperience: 0 })
    const result = validateCandidate(c)
    expect(result.valid).toBe(true)
  })

  it('accepts boundary yearsOfExperience = 50', () => {
    const c = createCandidate({ yearsOfExperience: 50 })
    const result = validateCandidate(c)
    expect(result.valid).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// validateVacancy
// ---------------------------------------------------------------------------
describe('validateVacancy', () => {
  it('returns valid for a correct vacancy', () => {
    const v = createVacancy()
    const result = validateVacancy(v)
    expect(result.valid).toBe(true)
    expect(result.errors).toEqual([])
  })

  it('returns error when requiredSkills is empty', () => {
    const v = createVacancy({ requiredSkills: [] })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Incluya al menos una de las habilidades necesarias para esta vacante')
  })

  it('returns error when minYearsExperience < 0', () => {
    const v = createVacancy({ minYearsExperience: -1 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('La experiencia mínima requerida debe de ser al menos 0 años')
  })

  it('returns error when maxYearsExperience < minYearsExperience', () => {
    const v = createVacancy({ minYearsExperience: 5, maxYearsExperience: 3 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('Los años de experiencia máxima deben ser igual o superiores a los años de experiencia mínima')
  })

  it('returns error when salaryRangeMax < salaryRangeMin', () => {
    const v = createVacancy({ salaryRangeMin: 8000, salaryRangeMax: 5000 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('El rango de salario máximo debe ser mayor que el rango de salario mínimo')
  })

  it('returns error when salaryRangeMax <= 0', () => {
    const v = createVacancy({ salaryRangeMax: 0 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('El salario máximo debe de ser superior a 0')
  })

  it('returns error when salaryRangeMin <= 0', () => {
    const v = createVacancy({ salaryRangeMin: 0 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('El salario mínimo debe de ser superior a 0')
  })

  it('accumulates multiple errors', () => {
    const v = createVacancy({
      requiredSkills: [],
      minYearsExperience: -1,
      maxYearsExperience: -5,
      salaryRangeMin: 0,
      salaryRangeMax: 0,
    })
    const result = validateVacancy(v)
    expect(result.valid).toBe(false)
    expect(result.errors.length).toBeGreaterThanOrEqual(5)
  })

  it('accepts boundary salaryRangeMin = 1', () => {
    const v = createVacancy({ salaryRangeMin: 1, salaryRangeMax: 100 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(true)
  })

  it('accepts boundary minYearsExperience = 0', () => {
    const v = createVacancy({ minYearsExperience: 0 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(true)
  })

  it('accepts equal min and max years experience', () => {
    const v = createVacancy({ minYearsExperience: 4, maxYearsExperience: 4 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(true)
  })

  it('accepts equal salaryRangeMin and salaryRangeMax', () => {
    const v = createVacancy({ salaryRangeMin: 5000, salaryRangeMax: 5000 })
    const result = validateVacancy(v)
    expect(result.valid).toBe(true)
  })
})