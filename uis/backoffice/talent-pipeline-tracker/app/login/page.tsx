import { AuthForm } from "@/components/auth/AuthForm";
import { hasSessionExpired } from "@/lib/auth-forms";

interface LoginPageProps {
  searchParams: Promise<{ expired?: string | string[] }>;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { expired } = await searchParams;
  return <AuthForm mode="login" expired={hasSessionExpired(expired)} />;
}