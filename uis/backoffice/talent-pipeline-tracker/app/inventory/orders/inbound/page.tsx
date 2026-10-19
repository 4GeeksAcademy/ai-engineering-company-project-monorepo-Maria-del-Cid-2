import { InboundFormPanel } from "@/components/inventory";

export default async function InboundOrderPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string | string[] }>;
}) {
  const { product } = await searchParams;
  const productId = Array.isArray(product) ? product[0] : product;

  return <InboundFormPanel initialProductId={productId ?? null} />;
}