export const candidates = [
    {
        id: "1",
        fullName: "Ana García",
        email: "ana@email.com",
        phone: "600123456",
        yearsOfExperience: 5,
        skills: ["JavaScript", "TypeScript", "React"],
        englishLevel: "C1",
        seniority: "Senior",
        currentSalary: 30000,
        expectedSalary: 35000,
        availability: "Immediate",
        location: "Madrid",
        remoteOnly: true,
        status: "Active"
    },
    {
        id: "2",
        fullName: "Carlos López",
        email: "carlos@email.com",
        phone: "600654321",
        yearsOfExperience: 2,
        skills: ["Python", "Java"],
        englishLevel: "B2",
        seniority: "Junior",
        currentSalary: 25000,
        expectedSalary: 28000,
        availability: "2 weeks",
        location: "Valencia",
        remoteOnly: false,
        status: "Active"
    },
    {
        id: "3",
        fullName: "Laura Martínez",
        email: "laura.martinez@email.com",
        phone: "611234567",
        yearsOfExperience: 8,
        skills: ["TypeScript", "React", "Node.js", "SQL"],
        englishLevel: "C2",
        seniority: "Senior",
        currentSalary: 42000,
        expectedSalary: 48000,
        availability: "2 weeks",
        location: "Barcelona, España",
        remoteOnly: true,
        status: "Active"
    },
    {
        id: "4",
        fullName: "David Sánchez",
        email: "david.sanchez@email.com",
        phone: "622345678",
        yearsOfExperience: 12,
        skills: ["Python", "Django", "PostgreSQL", "AWS"],
        englishLevel: "C1",
        seniority: "Lead",
        currentSalary: 50000,
        expectedSalary: 58000,
        availability: "1 month",
        location: "Madrid, España",
        remoteOnly: false,
        status: "In process"
    },
    {
        id: "5",
        fullName: "Sofía Rodríguez",
        email: "sofia.rodriguez@email.com",
        phone: "633456789",
        yearsOfExperience: 1,
        skills: ["JavaScript", "HTML", "CSS", "React"],
        englishLevel: "B2",
        seniority: "Junior",
        currentSalary: 22000,
        expectedSalary: 26000,
        availability: "Immediate",
        location: "Valencia, España",
        remoteOnly: true,
        status: "Hired"
    }
];
export const processes = [
    {
        id: "1",
        candidateId: "1",
        vacancyId: "1",
        stage: "Hired",
        score: 90,
        notes: "Candidato contratado",
        createdAt: new Date(),
        updatedAt: new Date()
    },
    {
        id: "2",
        candidateId: "2",
        vacancyId: "1",
        stage: "Interview",
        score: 75,
        notes: "Pendiente de entrevista",
        createdAt: new Date(),
        updatedAt: new Date()
    }
];
export const vacancies = [
    {
        id: "1",
        title: "Senior Full-Stack Developer",
        companyName: "TechCorp Solutions",
        requiredSkills: ["TypeScript", "React", "Node.js"],
        preferredSkills: ["PostgreSQL", "Docker"],
        minYearsExperience: 4,
        maxYearsExperience: 8,
        requiredEnglishLevel: "B2",
        requiredSeniority: "Senior",
        salaryRangeMin: 5000,
        salaryRangeMax: 7000,
        isRemote: true,
        location: "Remote",
        status: "Open"
    },
    {
        id: "2",
        title: "Junior Java Developer",
        companyName: "Innovatech",
        requiredSkills: ["Java", "Spring"],
        preferredSkills: ["SQL", "Docker"],
        minYearsExperience: 1,
        maxYearsExperience: 3,
        requiredEnglishLevel: "B1",
        requiredSeniority: "Junior",
        salaryRangeMin: 2500,
        salaryRangeMax: 3500,
        isRemote: false,
        location: "Valencia",
        status: "Open"
    }
];
