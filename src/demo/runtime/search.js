export function findCandidateById(candidates, id) {
  for (let i = 0; i < candidates.length; i++) {
    if (candidates[i].id === id) {
      return candidates[i];
    }
  }
  return null;
}

export function findCandidateByEmail(candidates, email) {
  for (let i = 0; i < candidates.length; i++) {
    if (candidates[i].email.toLowerCase() === email.toLowerCase()) {
      return candidates[i];
    }
  }
  return null;
}

export function binarySearchCandidateBySalary(sortedCandidates, targetSalary) {
  let left = 0;
  let right = sortedCandidates.length - 1;
  while (left <= right) {
    const middle = Math.floor((left + right) / 2);
    if (sortedCandidates[middle].expectedSalary === targetSalary) {
      return middle;
    } else if (sortedCandidates[middle].expectedSalary < targetSalary) {
      left = middle + 1;
    } else {
      right = middle - 1;
    }
  }
  return -1;
}
