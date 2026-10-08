import { PasswordResetForm } from "@/components/auth/PasswordResetForm";

interface ResetPasswordPageProps {
  searchParams: Promise<{ token?: string | string[] }>;
}

export default async function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const { token } = await searchParams;
  return <PasswordResetForm mode="reset" token={typeof token === "string" ? token : ""} />;
}
