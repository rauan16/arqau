export type PayFrequency = "Monthly" | "Twice a month" | "Weekly" | "It varies";
export type MonthlyIncomeRange = "Under 150,000 ₸" | "150,000-300,000 ₸" | "300,000-500,000 ₸" | "500,000-750,000 ₸" | "750,000 ₸+";
export type PaydayRange = "1st-5th" | "6th-15th" | "16th-25th" | "26th-31st" | "It varies";

export type OnboardingProfile = {
  name: string;
  payFrequency: PayFrequency;
  monthlyIncomeRange: MonthlyIncomeRange;
  paydayRange: PaydayRange;
  financialPressure: string;
  earlyAccessUseCase: string;
  aiHelpPreference: string;
};

export const onboardingStorageKey = "arqau-onboarding-profile";
