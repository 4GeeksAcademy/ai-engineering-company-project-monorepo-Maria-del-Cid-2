export function validateCandidate(candidate) {
  const errors = [];

  if (candidate.yearsOfExperience < 0 || candidate.yearsOfExperience > 50) {
    errors.push("Los años de experiencia deben de estar entre 0 y 50");
  }

  if (candidate.currentSalary <= 0) {
    errors.push("El salario actual debe de ser mayor que 0");
  }

  if (candidate.expectedSalary <= 0) {
    errors.push("El salario estimado debe de ser mayor que 0");
  }

  if (candidate.skills.length <= 0) {
    errors.push("Debe incluir al menos una habilidad");
  }

  if (!isValidEmail(candidate.email)) {
    errors.push("El correo electrónico introducido no es válido");
  }

  if (candidate.phone.length === 0) {
    errors.push("Debe incluir un número de telefono");
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

export function isValidEmail(email) {
  const atPosition = email.indexOf("@");
  const dotPosition = email.indexOf(".", atPosition);

  return atPosition > 0 && dotPosition > atPosition + 1;
}

export function validateVacancy(vacancy) {
  const errors = [];

  if (vacancy.requiredSkills.length <= 0) {
    errors.push("Incluya al menos una de las habilidades necesarias para esta vacante");
  }

  if (vacancy.minYearsExperience < 0) {
    errors.push("La experiencia mínima requerida debe de ser al menos 0 años");
  }

  if (vacancy.maxYearsExperience < vacancy.minYearsExperience) {
    errors.push("Los años de experiencia máxima deben ser igual o superiores a los años de experiencia mínima");
  }

  if (vacancy.salaryRangeMax < vacancy.salaryRangeMin) {
    errors.push("El rango de salario máximo debe ser mayor que el rango de salario mínimo");
  }

  if (vacancy.salaryRangeMax <= 0) {
    errors.push("El salario máximo debe de ser superior a 0");
  }

  if (vacancy.salaryRangeMin <= 0) {
    errors.push("El salario mínimo debe de ser superior a 0");
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
