export function filterCandidatesBySkills(candidates, requiredSkills) {
  return candidates.filter(candidate =>
    requiredSkills.every(requiredSkill =>
      candidate.skills.some(candidateSkill => candidateSkill.toLowerCase() === requiredSkill.toLowerCase())
    )
  );
}

export function filterCandidatesBySeniority(candidates, seniority) {
  return candidates.filter(candidate => candidate.seniority === seniority);
}

export function filterCandidatesByAvailability(candidates, availability) {
  return candidates.filter(candidate => availability.some(status => status === candidate.availability));
}

export function sortCandidatesBySalary(candidates, order) {
  const sortedCandidates = [...candidates];
  sortedCandidates.sort((a, b) => {
    if (order === "asc") {
      return a.expectedSalary - b.expectedSalary;
    }
    return b.expectedSalary - a.expectedSalary;
  });
  return sortedCandidates;
}

export function sortCandidatesByExperience(candidates, order) {
  const sortedCandidates = [...candidates];
  sortedCandidates.sort((a, b) => {
    if (order === "asc") {
      return a.yearsOfExperience - b.yearsOfExperience;
    }
    return b.yearsOfExperience - a.yearsOfExperience;
  });
  return sortedCandidates;
}
