import { AuthForm } from "@/components/auth/AuthForm";
import { hasSessionExpired } from "@/lib/auth-forms";

interface LoginPageProps {
  searchParams: Promise<{
    expired?: string | string[];
    reset?: string | string[];
    changed?: string | string[];
  }>;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { expired, reset, changed } = await searchParams;
  return (
    <AuthForm
      mode="login"
      expired={hasSessionExpired(expired)}
      reset={reset === "1"}
      changed={changed === "1"}
    />
  );
}