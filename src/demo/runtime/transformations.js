export function countCandidatesByStatus(candidates) {
  const result = {
    Active: 0,
    "In process": 0,
    Hired: 0,
    Inactive: 0
  };

  candidates.reduce((acumulador, candidate) => {
    acumulador[candidate.status]++;
    return acumulador;
  }, result);

  return result;
}

export function calculateAverageSalary(candidates) {
  if (candidates.length === 0) {
    return 0;
  }

  const totalSalary = candidates.reduce((total, candidate) => total + candidate.expectedSalary, 0);
  const averageSalary = totalSalary / candidates.length;

  return Number(averageSalary.toFixed(2));
}

export function findTopSkills(candidates, topN) {
  const skillCounts = {};

  candidates.forEach(candidate => {
    candidate.skills.forEach(skill => {
      if (skillCounts[skill]) {
        skillCounts[skill]++;
      } else {
        skillCounts[skill] = 1;
      }
    });
  });

  const skillsArray = Object.entries(skillCounts).map(([skill, count]) => ({ skill, count }));
  skillsArray.sort((a, b) => b.count - a.count);
  return skillsArray.slice(0, topN);
}

export function calculateVacancyFillRate(processes) {
  if (processes.length === 0) {
    return 0;
  }

  const hiredCount = processes.reduce((count, process) => {
    if (process.stage === "Hired") {
      return count + 1;
    }
    return count;
  }, 0);

  const fillRate = (hiredCount / processes.length) * 100;
  return Number(fillRate.toFixed(2));
}

export function calculateCandidateScore(candidate, vacancy) {
  let score = 0;

  const matchedRequiredSkills = vacancy.requiredSkills.filter(requiredSkill =>
    candidate.skills.some(candidateSkill => candidateSkill.toLowerCase() === requiredSkill.toLowerCase())
  );

  const requiredSkillsPercentage = matchedRequiredSkills.length / vacancy.requiredSkills.length;

  if (requiredSkillsPercentage === 1) {
    score += 40;
  } else if (requiredSkillsPercentage >= 0.5) {
    score += 20;
  }

  const matchedPreferredSkills = vacancy.preferredSkills.filter(preferredSkill =>
    candidate.skills.some(candidateSkill => candidateSkill.toLowerCase() === preferredSkill.toLowerCase())
  );

  score += Math.min(matchedPreferredSkills.length * 10, 20);

  if (candidate.yearsOfExperience >= vacancy.minYearsExperience && candidate.yearsOfExperience <= vacancy.maxYearsExperience) {
    score += 20;
  } else {
    const difference =
      candidate.yearsOfExperience < vacancy.minYearsExperience
        ? vacancy.minYearsExperience - candidate.yearsOfExperience
        : candidate.yearsOfExperience - vacancy.maxYearsExperience;

    if (difference <= 2) {
      score += 10;
    }
  }

  const seniorityLevels = ["Junior", "Semi-Senior", "Senior", "Lead", "Executive"];
  const candidateSeniorityIndex = seniorityLevels.indexOf(candidate.seniority);
  const vacancySeniorityIndex = seniorityLevels.indexOf(vacancy.requiredSeniority);
  const seniorityDifference = Math.abs(candidateSeniorityIndex - vacancySeniorityIndex);

  if (seniorityDifference === 0) {
    score += 15;
  } else if (seniorityDifference === 1) {
    score += 7;
  }

  const englishLevels = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"];
  const candidateEnglishIndex = englishLevels.indexOf(candidate.englishLevel);
  const vacancyEnglishIndex = englishLevels.indexOf(vacancy.requiredEnglishLevel);

  if (candidateEnglishIndex >= vacancyEnglishIndex) {
    score += 15;
  }

  if (candidate.expectedSalary >= vacancy.salaryRangeMin && candidate.expectedSalary <= vacancy.salaryRangeMax) {
    score += 10;
  } else if (
    candidate.expectedSalary > vacancy.salaryRangeMax &&
    candidate.expectedSalary <= vacancy.salaryRangeMax * 1.2
  ) {
    score += 5;
  }

  return score;
}

export function rankCandidatesForVacancy(candidates, vacancy) {
  const rankedCandidates = candidates.map(candidate => {
    return {
      candidate,
      score: calculateCandidateScore(candidate, vacancy)
    };
  });

  rankedCandidates.sort((a, b) => b.score - a.score);
  return rankedCandidates;
}

export function groupCandidatesBySeniority(candidates) {
  const result = {
    Junior: [],
    "Semi-Senior": [],
    Senior: [],
    Lead: [],
    Executive: []
  };

  candidates.forEach(candidate => {
    result[candidate.seniority].push(candidate);
  });

  return result;
}
